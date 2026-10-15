const http = require('http');
const express = require('express');
const WebSocket = require('ws');
const crypto = require('crypto');
const basicAuth = require('./basic-auth');
const license = require('./license');
const mailer = require('./mailer');
const monitor = require('./monitor');
const abuseMonitor = require('./abuse-monitor');

const PORT = process.env.PORT || 8080;
const TECHNICIAN_TOKEN = process.env.TECHNICIAN_TOKEN || '';

// ============================================================
// 1. SERVIDOR HTTP (Express) — licenças, webhook, admin
// ============================================================
const app = express();
app.set('trust proxy', true);
app.use(express.json({ verify: (req, res, buf) => { req.rawBody = buf; } }));

app.get('/', (req, res) => {
  res.send('Remote Access App - servidor no ar.');
});

// ---- Verificação de versão do app ----
app.get('/version', (req, res) => {
  res.json({
    latestVersion: process.env.APP_LATEST_VERSION || '1.0.0',
    minRequiredVersion: process.env.APP_MIN_VERSION || '1.0.0',
    downloadUrl: process.env.APP_DOWNLOAD_URL || '',
  });
});

// ---- Idempotência do webhook: guarda pedidos já processados ----
const processedOrders = new Map(); // orderId -> timestamp
const PROCESSED_ORDERS_MAX = 5000;
const PROCESSED_ORDERS_TTL_MS = 24 * 60 * 60 * 1000; // 24 horas

function markOrderProcessed(orderId) {
  const now = Date.now();
  processedOrders.set(orderId, now);
  if (processedOrders.size > PROCESSED_ORDERS_MAX) {
    for (const [id, ts] of processedOrders) {
      if (now - ts > PROCESSED_ORDERS_TTL_MS) processedOrders.delete(id);
      if (processedOrders.size <= PROCESSED_ORDERS_MAX) break;
    }
  }
}

function isOrderProcessed(orderId) {
  const ts = processedOrders.get(orderId);
  if (!ts) return false;
  if (Date.now() - ts > PROCESSED_ORDERS_TTL_MS) {
    processedOrders.delete(orderId);
    return false;
  }
  return true;
}

// ---- Comparação de assinatura em tempo constante ----
function safeCompare(a, b) {
  const bufA = Buffer.from(String(a));
  const bufB = Buffer.from(String(b));
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

// ---- Webhook da Kiwify ----
app.post('/webhook/kiwify', async (req, res) => {
  const token = process.env.KIWIFY_WEBHOOK_TOKEN;
  const receivedSignature = req.query.signature || null;
  const rawBody = req.rawBody ? req.rawBody.toString('utf8') : JSON.stringify(req.body);

  const hmacSha1 = crypto.createHmac('sha1', token || '').update(rawBody).digest('hex');

  if (!token || !receivedSignature || !safeCompare(receivedSignature, hmacSha1)) {
    console.warn('[webhook kiwify] assinatura inválida ou ausente.');
    return res.status(401).send('unauthorized');
  }

  try {
    const body = req.body || {};
    const email = body.Customer?.email || body.customer?.email || body.customer_email || body.email || null;
    const productId = body.Product?.product_id || body.product?.id || body.product_id || body.ProductId || null;
    const orderId = body.order_id || body.OrderId || body.id || null;
    const eventType = body.webhook_event_type || body.event || body.order_status || 'desconhecido';

    // log enxuto: sem headers nem payload completo (dados do comprador)
    console.log(`[webhook kiwify] evento=${eventType} productId=${productId} orderId=${orderId} email=${email}`);

    const NEW_PRODUCT_ID = process.env.KIWIFY_PRODUCT_ID_NEW;
    const RENEWAL_PRODUCT_ID = process.env.KIWIFY_PRODUCT_ID_RENEWAL;

    const approvedEvents = ['compra_aprovada', 'purchase.approved', 'paid', 'approved'];
    const isApproved = approvedEvents.some((e) => String(eventType).toLowerCase().includes(e.toLowerCase()));

    if (!isApproved) {
      console.log('[webhook kiwify] evento ignorado (não é aprovação de compra).');
      return res.status(200).send('ignored');
    }

    // reenvio da Kiwify: se o pedido já foi processado, ignora
    if (orderId && isOrderProcessed(String(orderId))) {
      console.log(`[webhook kiwify] pedido ${orderId} já processado — reenvio ignorado.`);
      return res.status(200).send('already-processed');
    }
    if (orderId) markOrderProcessed(String(orderId));

    if (productId && RENEWAL_PRODUCT_ID && String(productId) === String(RENEWAL_PRODUCT_ID)) {
      const licenseKeyField = body.licenseKey || body.custom_fields?.licenseKey || null;
      let updated = null;
      if (licenseKeyField) {
        updated = license.extendLicenseByKey(licenseKeyField);
      } else if (email) {
        updated = license.extendLicenseByEmail(email);
      }
      if (updated) {
        res.status(200).send('ok'); // responde na hora
        mailer.sendRenewalEmail(email, updated.key, updated.expiresAt)
          .catch((e) => console.error('[webhook kiwify] falha ao enviar e-mail de renovação:', e));
        console.log(`[webhook kiwify] renovação processada para ${updated.key}`);
      } else {
        console.warn('[webhook kiwify] não foi possível encontrar a licença para renovar.');
        await mailer.sendAdminAlert(
          'Renovação não encontrou a licença',
          `Uma renovação foi aprovada, mas nenhuma licença foi encontrada.\n` +
          `E-mail do comprador: ${email}\nPedido: ${orderId}\n` +
          `Chave informada no checkout: ${licenseKeyField || 'nenhuma'}\n\n` +
          `Provável causa: o cliente comprou a renovação com um e-mail diferente do da licença.`
        );
        res.status(200).send('ok');
      }
    } else if (productId && NEW_PRODUCT_ID && String(productId) === String(NEW_PRODUCT_ID)) {
      const created = license.createLicense(email, orderId);
      res.status(200).send('ok'); // responde na hora; e-mail vai em segundo plano
      mailer.sendLicenseEmail(email, created.key)
        .catch((e) => console.error('[webhook kiwify] falha ao enviar e-mail de licença:', e));
      console.log(`[webhook kiwify] licença nova criada: ${created.key}`);
    } else {
      console.warn(
        `[webhook kiwify] productId (${productId}) não corresponde a KIWIFY_PRODUCT_ID_NEW nem ` +
        `KIWIFY_PRODUCT_ID_RENEWAL. Nenhuma licença foi criada ou renovada.`
      );
      await mailer.sendAdminAlert(
        'Webhook da Kiwify com productId desconhecido',
        `Uma compra foi aprovada, mas o productId (${productId}) não bate com nenhum produto ` +
        `configurado (KIWIFY_PRODUCT_ID_NEW ou KIWIFY_PRODUCT_ID_RENEWAL).\n\n` +
        `E-mail do comprador: ${email}\nPedido: ${orderId}\n\n` +
        `Nenhuma licença foi criada automaticamente — confira manualmente e corrija as variáveis de ambiente se necessário.`
      );
      res.status(200).send('ok');
    }
  } catch (e) {
    console.error('[webhook kiwify] erro ao processar:', e);
    if (!res.headersSent) res.status(500).send('error');
  }
});

// ---- API de licenças (usada pelo app do cliente) ----
app.post('/license/activate', async (req, res) => {
  const { licenseKey, machineFingerprint, machineName } = req.body || {};
  if (!licenseKey || !machineFingerprint) {
    return res.status(400).json({ ok: false, reason: 'missing_fields' });
  }
  const result = license.activateLicense(licenseKey, machineFingerprint, machineName);
  if (!result.ok) {
    await abuseMonitor.recordFailedActivation({
      key: licenseKey,
      fingerprint: machineFingerprint,
      ip: req.ip,
      reason: result.reason,
    });
  }
  res.json(result);
});

app.post('/license/validate', (req, res) => {
  const { licenseKey, machineFingerprint } = req.body || {};
  if (!licenseKey || !machineFingerprint) {
    return res.status(400).json({ valid: false, reason: 'missing_fields' });
  }
  const result = license.validateLicense(licenseKey, machineFingerprint);
  res.json(result);
});

// ---- Painel administrativo (protegido por senha) ----
// Falha fechada: sem ADMIN_PASSWORD configurada, o painel fica bloqueado
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || '';
const adminAuth = basicAuth({
  user: process.env.ADMIN_USER || 'admin',
  password: ADMIN_PASSWORD,
});

if (!ADMIN_PASSWORD) {
  console.error('ERRO: ADMIN_PASSWORD não configurada. O painel /admin ficará BLOQUEADO até a variável ser definida.');
}

function adminGuard(req, res, next) {
  if (!ADMIN_PASSWORD) {
    return res.status(503).send('Painel admin desativado: configure ADMIN_PASSWORD no servidor.');
  }
  adminAuth(req, res, next);
}

app.get('/admin', adminGuard, (req, res) => {
  res.sendFile(require('path').join(__dirname, 'admin.html'));
});

app.get('/admin/api/licenses', adminGuard, (req, res) => {
  res.json(license.listAllLicenses());
});

// ---- Criação manual de licença (pelo dono, via painel admin) ----
app.post('/admin/api/licenses/reset-machine', adminGuard, (req, res) => {
  const { key } = req.body || {};
  const result = license.resetMachine(key);
  console.log(`[admin] reset de máquinas da licença ${key}: ${result.ok ? 'ok' : result.reason}`);
  res.json(result);
});

// ---- Exportação CSV com escape correto ----
function csvField(value) {
  const s = String(value == null ? '' : value);
  return `"${s.replace(/"/g, '""')}"`;
}

app.get('/admin/api/export.csv', adminGuard, (req, res) => {
  const licenses = license.listAllLicenses();
  const header = 'email,chave,status,criado_em,ativado_em,expira_em\n';
  const rows = licenses
    .map((l) =>
      [csvField(l.email || ''), csvField(l.key), csvField(l.status), csvField(l.createdAt), csvField(l.activatedAt || ''), csvField(l.expiresAt || '')].join(',')
    )
    .join('\n');
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="clientes.csv"');
  res.send(header + rows);
});

app.get('/admin/api/system-status', adminGuard, (req, res) => {
  res.json(monitor.getCurrentStatus(wss));
});

app.get('/admin/api/export-json', adminGuard, (req, res) => {
  const backup = license.exportAll();
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="henndesk_backup_${Date.now()}.json"`);
  res.send(JSON.stringify(backup, null, 2));
});

// ============================================================
// 2. SERVIDOR DE SINALIZAÇÃO (WebSocket)
// ============================================================
const httpServer = http.createServer(app);
const wss = new WebSocket.Server({ server: httpServer });
monitor.startMonitoring(wss);

const agents = new Map();
const pendingTechnicians = new Map(); // targetId -> { ws, timer }
const technicians = new Set();

if (!TECHNICIAN_TOKEN) {
  console.warn('AVISO: TECHNICIAN_TOKEN não configurada — ações de técnico NÃO exigem token. Configure a variável na Render.');
}

function technicianAuthorized(msg) {
  if (!TECHNICIAN_TOKEN) return true;
  const received = msg && msg.technicianToken ? String(msg.technicianToken) : '';
  if (received === TECHNICIAN_TOKEN) return true;
  console.warn(
    `[ws] TOKEN RECUSADO — recebido: "${received.slice(0, 4)}" (tamanho ${received.length}) | ` +
    `esperado: "${TECHNICIAN_TOKEN.slice(0, 4)}" (tamanho ${TECHNICIAN_TOKEN.length})`
  );
  return false;
}

function send(ws, data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

function generateId() {
  let id;
  do {
    id = Math.floor(100000000 + Math.random() * 900000000).toString();
  } while (agents.has(id));
  return id;
}

function broadcastAgents() {
  const list = Array.from(agents.keys());
  const payload = JSON.stringify({ type: 'agents-updated', agents: list });
  for (const tech of technicians) {
    if (tech.readyState === WebSocket.OPEN) tech.send(payload);
  }
}

wss.on('connection', (ws) => {
  ws.role = null;
  ws.machineId = null;

  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch (e) {
      return;
    }

    switch (msg.type) {
      case 'register-agent': {
        const id = msg.machineId && !agents.has(msg.machineId) ? msg.machineId : generateId();
        ws.role = 'agent';
        ws.machineId = id;
        agents.set(id, { ws, connectedTechnician: null, lastTechnician: null });
        send(ws, { type: 'registered', machineId: id });
        console.log(`[agente registrado] ID ${id}`);
        broadcastAgents();
        break;
      }

      case 'list-agents': {
        if (!technicianAuthorized(msg)) {
          send(ws, { type: 'error', code: 'unauthorized' });
          return;
        }
        ws.role = 'technician';
        technicians.add(ws);
        send(ws, { type: 'agents-updated', agents: Array.from(agents.keys()) });
        break;
      }

      case 'request-connect': {
        if (!technicianAuthorized(msg)) {
          send(ws, { type: 'error', code: 'unauthorized' });
          return;
        }
        ws.role = 'technician';
        technicians.add(ws);

        const target = agents.get(msg.targetId);
        if (!target) {
          send(ws, { type: 'error', code: 'id_not_found' });
          return;
        }

        // pedido pendente expira em 60 segundos
        const timer = setTimeout(() => {
          const pending = pendingTechnicians.get(msg.targetId);
          if (pending && pending.ws === ws) {
            pendingTechnicians.delete(msg.targetId);
            console.log(`[pedido de conexão] expirado para ${msg.targetId}`);
          }
        }, 60000);

        pendingTechnicians.set(msg.targetId, { ws, timer });
        send(target.ws, { type: 'incoming-request', technicianName: msg.technicianName || 'Técnico' });
        console.log(`[pedido de conexão] técnico -> ${msg.targetId}`);
        break;
      }

      case 'respond-request': {
        const pending = pendingTechnicians.get(ws.machineId);
        pendingTechnicians.delete(ws.machineId);
        if (!pending) return;
        clearTimeout(pending.timer);
        const techWs = pending.ws;

        if (msg.accepted) {
          const agent = agents.get(ws.machineId);
          if (agent) {
            agent.connectedTechnician = techWs;
            agent.lastTechnician = techWs;
          }
          send(techWs, { type: 'request-accepted', targetId: ws.machineId });
          console.log(`[aceito] ${ws.machineId} aceitou a conexão`);
        } else {
          send(techWs, { type: 'request-declined', targetId: ws.machineId });
          console.log(`[recusado] ${ws.machineId} recusou a conexão`);
        }
        break;
      }

      case 'signal': {
        const target = agents.get(msg.targetId);
        if (target && target.ws !== ws) {
          send(target.ws, { type: 'signal', payload: msg.payload, from: ws.machineId || 'technician' });
        } else if (ws.role === 'agent') {
          const agent = agents.get(ws.machineId);
          if (agent && agent.connectedTechnician) {
            send(agent.connectedTechnician, { type: 'signal', payload: msg.payload, from: ws.machineId });
          }
        }
        break;
      }

      case 'end-session': {
        if (ws.role === 'agent') {
          const agent = agents.get(ws.machineId);
          if (agent && agent.connectedTechnician) {
            send(agent.connectedTechnician, { type: 'session-ended' });
            agent.connectedTechnician = null;
          }
        } else {
          const target = agents.get(msg.targetId);
          if (target) {
            send(target.ws, { type: 'session-ended' });
            target.connectedTechnician = null;
          }
        }
        break;
      }

      case 'submit-rating': {
        if (ws.role === 'agent') {
          const agent = agents.get(ws.machineId);
          if (agent && agent.lastTechnician) {
            send(agent.lastTechnician, {
              type: 'rating-received',
              rating: msg.rating,
              comment: msg.comment || '',
              fromId: ws.machineId,
            });
            console.log(`[avaliação] ${ws.machineId} avaliou com ${msg.rating} estrela(s)`);
          }
        }
        break;
      }

      default:
        break;
    }
  });

  ws.on('close', () => {
    if (ws.role === 'agent' && ws.machineId) {
      const pending = pendingTechnicians.get(ws.machineId);
      if (pending) {
        clearTimeout(pending.timer);
        pendingTechnicians.delete(ws.machineId);
      }
      agents.delete(ws.machineId);
      console.log(`[agente desconectado] ID ${ws.machineId}`);
      broadcastAgents();
    }
    if (ws.role === 'technician') {
      technicians.delete(ws);
    }
  });
});

httpServer.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT} (sinalização + licenças + admin)`);
});