/**
 * Detecção de uso suspeito de licenças.
 *
 * Fica de olho em dois padrões que costumam indicar pirataria ou vazamento
 * de chave:
 *   1. A MESMA chave sendo tentada em várias máquinas diferentes (fingerprints
 *      distintos) num curto período — sinal de chave compartilhada/vazada.
 *   2. O MESMO IP tentando várias chaves inválidas em sequência — sinal de
 *      tentativa de "adivinhar" uma chave válida (força bruta).
 *
 * Guardado apenas em memória (reinicia com o servidor) — é o suficiente
 * para detectar picos de abuso em tempo real, sem precisar de banco de dados.
 */

const mailer = require('./mailer');

const SAME_KEY_DISTINCT_FINGERPRINTS_THRESHOLD = 3; // fingerprints diferentes tentando a mesma chave
const SAME_KEY_WINDOW_MS = 24 * 60 * 60 * 1000; // 24 horas

const BRUTE_FORCE_ATTEMPTS_THRESHOLD = 10; // tentativas de chave inexistente
const BRUTE_FORCE_WINDOW_MS = 60 * 60 * 1000; // 1 hora

const failedKeyAttempts = new Map(); // key -> [{ fingerprint, ip, timestamp }]
const notFoundAttemptsByIp = new Map(); // ip -> [timestamp]

const alertedKeys = new Set(); // evita alertar a mesma chave repetidamente
const alertedIps = new Set();

function pruneOld(list, windowMs) {
  const cutoff = Date.now() - windowMs;
  return list.filter((entry) => entry.timestamp >= cutoff || entry >= cutoff);
}

async function recordFailedActivation({ key, fingerprint, ip, reason }) {
  const now = Date.now();

  if (reason === 'already_activated_elsewhere') {
    const attempts = failedKeyAttempts.get(key) || [];
    attempts.push({ fingerprint, ip, timestamp: now });
    const recent = pruneOld(attempts, SAME_KEY_WINDOW_MS);
    failedKeyAttempts.set(key, recent);

    const distinctFingerprints = new Set(recent.map((a) => a.fingerprint));
    if (distinctFingerprints.size >= SAME_KEY_DISTINCT_FINGERPRINTS_THRESHOLD && !alertedKeys.has(key)) {
      alertedKeys.add(key);
      console.warn(`[abuso] Chave ${key} tentada em ${distinctFingerprints.size} máquinas diferentes.`);
      await mailer.sendAdminAlert(
        'Possível licença compartilhada/vazada',
        `A chave ${key} foi tentada em ${distinctFingerprints.size} computadores diferentes ` +
        `nas últimas 24 horas (cada tentativa foi recusada corretamente, já que a chave só ` +
        `pode estar ativa em um computador por vez).\n\n` +
        `Isso pode indicar que essa chave foi compartilhada ou vazada.\n\n` +
        `IPs envolvidos: ${[...new Set(recent.map((a) => a.ip))].join(', ')}`
      );
    }
  }

  if (reason === 'not_found' && ip) {
    const attempts = notFoundAttemptsByIp.get(ip) || [];
    attempts.push(now);
    const recent = pruneOld(attempts, BRUTE_FORCE_WINDOW_MS);
    notFoundAttemptsByIp.set(ip, recent);

    if (recent.length >= BRUTE_FORCE_ATTEMPTS_THRESHOLD && !alertedIps.has(ip)) {
      alertedIps.add(ip);
      console.warn(`[abuso] IP ${ip} tentou ${recent.length} chaves inexistentes na última hora.`);
      await mailer.sendAdminAlert(
        'Possível tentativa de força bruta em licenças',
        `O endereço IP ${ip} tentou ativar ${recent.length} chaves de licença inexistentes ` +
        `na última hora.\n\nIsso pode indicar uma tentativa de "adivinhar" uma chave válida.`
      );
    }
  }
}

module.exports = { recordFailedActivation };
