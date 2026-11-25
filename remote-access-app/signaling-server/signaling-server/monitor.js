/**
 * Monitoramento de recursos do servidor.
 *
 * O Render não avisa proativamente quando o plano está ficando apertado —
 * então este módulo confere periodicamente o uso de RAM deste processo e
 * dispara um alerta por e-mail (uma vez, não repetidamente) quando passa
 * de 70% do limite do plano contratado.
 *
 * Configure no Render (Environment):
 *   RENDER_INSTANCE_RAM_MB -> limite de RAM do plano contratado, em MB
 *                             (ex: 512 para o plano Starter de $7/mês)
 */

const mailer = require('./mailer');

const RAM_LIMIT_MB = parseInt(process.env.RENDER_INSTANCE_RAM_MB || '512', 10);
const ALERT_THRESHOLD_PERCENT = 70;
const CHECK_INTERVAL_MS = 15 * 60 * 1000; // a cada 15 minutos
const RE_ALERT_COOLDOWN_MS = 6 * 60 * 60 * 1000; // não repete o alerta por 6 horas

let lastAlertSentAt = null;

function getCurrentStatus(wss) {
  const memUsage = process.memoryUsage();
  const usedMB = Math.round(memUsage.rss / 1024 / 1024);
  const percentUsed = Math.round((usedMB / RAM_LIMIT_MB) * 100);
  const connectedClients = wss ? wss.clients.size : 0;

  return {
    usedMB,
    limitMB: RAM_LIMIT_MB,
    percentUsed,
    connectedClients,
    isAboveThreshold: percentUsed >= ALERT_THRESHOLD_PERCENT,
  };
}

async function checkAndAlert(wss) {
  const status = getCurrentStatus(wss);

  if (status.isAboveThreshold) {
    const now = Date.now();
    const canSendAgain = !lastAlertSentAt || (now - lastAlertSentAt) > RE_ALERT_COOLDOWN_MS;

    if (canSendAgain) {
      console.warn(`[monitor] RAM em ${status.percentUsed}% (${status.usedMB}MB de ${status.limitMB}MB) — enviando alerta.`);
      const sent = await mailer.sendAdminAlert(
        'Servidor HennAccess está ficando sem RAM',
        `O servidor está usando ${status.usedMB}MB de ${status.limitMB}MB (${status.percentUsed}%).\n\n` +
        `Clientes conectados agora: ${status.connectedClients}\n\n` +
        `Recomendação: considere fazer upgrade do plano no Render antes que o servidor fique instável.\n` +
        `Acesse o painel do Render para fazer o upgrade (é rápido, sem precisar mudar código).`
      );
      if (sent) lastAlertSentAt = now;
    }
  } else {
    // se voltou a ficar saudável, permite alertar de novo caso suba de novo no futuro
    lastAlertSentAt = null;
  }

  return status;
}

function startMonitoring(wss) {
  setInterval(() => {
    checkAndAlert(wss).catch((e) => console.error('[monitor] erro ao checar status:', e));
  }, CHECK_INTERVAL_MS);
  console.log(`[monitor] Monitoramento de RAM ativo (limite: ${RAM_LIMIT_MB}MB, alerta em ${ALERT_THRESHOLD_PERCENT}%).`);
}

module.exports = { startMonitoring, getCurrentStatus };
