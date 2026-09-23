/**
 * Servidor principal - Remote Access App
 *
 * Reúne três funções no mesmo serviço (mesmo endereço do Render):
 *   1. Sinalização WebRTC (para o app conectar técnico <-> cliente)
 *   2. API de licenças (ativação, validação)
 *   3. Webhook da Kiwify + painel administrativo
 */
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
// ============================================================
// 1. SERVIDOR HTTP (Express) — licenças, webhook, admin
// ============================================================
const app = express();
app.set('trust proxy', true); // necessário para req.ip mostrar o IP real do cliente (Render fica atrás de um proxy)
app.use(express.json({
  verify: (req, res, buf) => { req.rawBody = buf; }
}));
app.get('/', (req, res) => {
  res.send('Remote Access App - servidor no ar.');
});
// ---- Verificação de versão do app ----
// Configure no Render: APP_LATEST_VERSION, APP_MIN_VERSION, APP_DOWNLOAD_URL
app.get('/version', (req, res) => {
  res.json({
    latestVersion: process.env.APP_LATEST_VERSION || '1.0.0',
    minRequiredVersion: process.env.APP_MIN_VERSION || '1.0.0',
    downloadUrl: process.env.APP_DOWNLOAD_URL || '',
  });
});
// ---- Webhook da Kiwify ----
// Configure na Kiwify a URL como: https://SEU-SERVICO.onrender.com/webhook/kiwify
// A Kiwify envia a assinatura no parâmetro de query "signature"
// (40 caracteres hexadecimais = SHA1). Validamos com HMAC-SHA1 do corpo
// bruto usando o token (KIWIFY_WEBHOOK_TOKEN) como chave.
app.post('/webhook/kiwify', async (req, res) => {
  // Registra tudo ANTES de validar a assinatura — assim, mesmo que a
  // validação falhe, conseguimos ver exatamente o formato real que a
  // Kiwify mandou (cabeçalhos e corpo), o que é essencial pra confirmar
  // o algoritmo e ajustar o parsing dos campos abaixo se necessário.
  console.log('[webhook kiwify] headers recebidos:', JSON.stringify(req.headers));
  console.log('[webhook kiwify] query recebida:', JSON.stringify(req.query));
  console.log('[webhook kiwify] payload recebido:', JSON.stringify(req.body));

  const token = process.env.KIWIFY_WEBHOOK_TOKEN;
  const receivedSignature = req.query.signature || null;
  const rawBody = req.rawBody ? req.rawBody.toString('utf8') : JSON.stringify(req.body);

  // Calcula variações para diagnóstico — se a primeira tentativa não bater,
  // os logs mostram qual algoritmo a Kiwify realmente usa.
  const hmacSha1 = crypto.createHmac('sha1', token || '').update(rawBody).digest('hex');
  const sha1Plain = crypto.createHash('sha1').update(rawBody).digest('hex');
  const hmacSha256 = crypto.createHmac('sha256', token || '').update(rawBody).digest('hex');

  console.log('[webhook kiwify] assinatura recebida:', receivedSignature);
  console.log('[webhook kiwify] HMAC-SHA1 calculado:', hmacSha1);
  console.log('[webhook kiwify] SHA1 puro calculado:', sha1Plain);
  console.log('[webhook kiwify] HMAC-SHA256 calculado:', hmacSha256);

  if (!token || !receivedSignature || receivedSignature !== hmacSha1) {
    console.warn('[webhook kiwify] assinatura inválida ou ausente.');
    return res.status(401).send('unauthorized');
  }

  try {
    const body = req.body || {};
    // Tenta localizar os campos em alguns formatos comuns — ajustaremos com base no teste real.
    const email =
      body.Customer?.email || body.customer?.email || body.customer_email || body.email || null;
    const productId =
      body.Product?.product_id || body.product?.id || body.product_id || body.ProductId || null;
    const orderId = body.order_id || body.OrderId || body.id || null;
    const eventType = body.webhook_event_type || body.event || body.order_status || 'desconhecido';
    console.log(`[webhook kiwify] evento=${eventType} email=${email} productId=${productId}`);
    const NEW_PRODUCT_ID = process.env.KIWIFY_PRODUCT_ID_NEW;
    const RENEWAL_PRODUCT_ID = process.env.KIWIFY_PRODUCT_ID_RENEWAL;
    const approvedEvents = ['compra_aprovada', 'purchase.approved', 'paid', 'approved'];
    const isApproved = approvedEvents.some((e) => String(eventType).toLowerCase().includes(e.toLowerCase()));
    if (!isApproved) {
      console.log('[webhook kiwify] evento ignorado (não é aprovação de compra).');
      return res.status(200).send('ignored');
    }
    if (productId && RENEWAL_PRODUCT_ID && String(productId) === String(RENEWAL_PRODUCT_ID)) {
      // Renovação
      const licenseKeyField = body.licenseKey || body.custom_fields?.licenseKey || null;
      let updated = null;
      if (licenseKeyField) {
        updated = license.extendLicenseByKey(licenseKeyField);
      } else if (email) {
        updated = license.extendLicenseByEmail(email);
      }
      if (updated) {
        await mailer.sendRenewalEmail(email, updated.key, updated.expiresAt);
        console.log(`[webhook kiwify] renovação processada para ${updated.key}`);
      } else {
        console.warn('[webhook kiwify] não foi possível encontrar a licença para renovar.');
      }
    } else if (productId && NEW_PRODUCT_ID && String(productId) === String(NEW_PRODUCT_ID)) {
      // Instalação nova
      const created = license.createLicense(email, orderId);
      await mailer.sendLicenseEmail(email, created.key);
      console.log(`[webhook kiwify] licença nova criada: ${created.key}`);
    } else {
      // productId não bate com nenhum dos dois IDs conhecidos — não arrisca criar/renovar errado
      console.warn(
        `[webhook kiwify] productId (${productId}) não corresponde a KIWIFY_PRODUCT_ID_NEW nem ` +
        `KIWIFY_PRODUCT_ID_RENEWAL. Nenhuma licença foi criada ou renovada. Confira as variáveis de ambiente.`
      );
      await mailer.sendAdminAlert(
        'Webhook da Kiwify com productId desconhecido',
        `Uma compra foi aprovada, mas o productId (${productId}) não bate com nenhum produto ` +
        `configurado (KIWIFY_PRODUCT_ID_NEW ou KIWIFY_PRODUCT_ID_RENEWAL).\n\n` +
        `E-mail do comprador: ${email}\nPedido: ${orderId}\n\n` +
        `Nenhuma licença foi criada automaticamente — confira manualmente e corrija as variáveis de ambiente se necessário.`
      );
    }
    res.status(200).send('ok');
  } catch (e) {
    console.error('[webhook kiwify] erro ao processar:', e);
    res.status(500).send('error');
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
const adminAuth = basicAuth({
  user: process.env.ADMIN_USER || 'admin',
  password: process.env.ADMIN_PASSWORD || 'troque-esta-senha',
});
app.get('/admin', adminAuth, (req, res) => {
  res.sendFile(require('path').join(__dirname, 'admin.html'));
});
app.get('/admin/api/licenses', adminAuth, (req, res) => {
  res.json(license.listAllLicenses());
});
app.get('/admin/api/export.csv', adminAuth, (req, res) => {
  const licenses = license.listAllLicenses();
  const header = 'email,chave,status,criado_em,ativado_em,expira_em\n';
  const rows = licenses
    .map((l) => [l.email || '', l.key, l.status, l.createdAt, l.activatedAt || '', l.expiresAt || ''].join(','))
    .join('\n');
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="clientes.csv"');
  res.send(header + rows);
});
app.get('/admin/api/system-status', adminAuth, (req, res) => {
  res.json(monitor.getCurrentStatus(wss));
});
app.get('/admin/api/export-json', adminAuth, (req, res) => {
  const backup = license.exportAll();
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="henndesk_backup_${Date.now()}.json"`);
  res.send(JSON.stringify(backup, null, 2));
});
// ============================================================
// 2. SERVIDOR DE SINALIZAÇÃO (WebSocket) — igual ao que já tínhamos
// ============================================================
const httpServer = http.createServer(app);
const wss = new WebSocket.Server({ server: httpServer });
monitor.startMonitoring(wss);
const agents = new Map();
const pendingTechnicians = new Map();
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
        break;
      }
      case 'request-connect': {
        ws.role = 'technician';
        const target = agents.get(msg.targetId);
        if (!target) {
          send(ws, { type: 'error', code: 'id_not_found' });
          return;
        }
        pendingTechnicians.set(msg.targetId, ws);
        send(target.ws, {
          type: 'incoming-request',
          technicianName: msg.technicianName || 'Técnico',
        });
        console.log(`[pedido de conexão] técnico -> ${msg.targetId}`);
        break;
      }
      case 'respond-request': {
        const techWs = pendingTechnicians.get(ws.machineId);
        pendingTechnicians.delete(ws.machineId);
        if (!techWs) return;
        if (msg.accepted) {
          const agent = agents.get(ws.machineId);
          if (agent) {
            agent.connectedTechnician = techWs;
            agent.lastTechnician = techWs; // mantido mesmo após o fim da sessão, para permitir avaliação
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
        // Enviada pelo cliente (agente) logo após o fim de uma sessão.
        // Usa lastTechnician (não connectedTechnician) porque a essa altura
        // a sessão já pode ter sido oficialmente encerrada.
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
      agents.delete(ws.machineId);
      pendingTechnicians.delete(ws.machineId);
      console.log(`[agente desconectado] ID ${ws.machineId}`);
    }
  });
});
httpServer.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT} (sinalização + licenças + admin)`);
});