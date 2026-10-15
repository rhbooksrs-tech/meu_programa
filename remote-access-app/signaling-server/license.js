/**
 * Módulo de licenças - armazenamento em arquivo JSON local.
 *
 * Guardado em disco persistente do Render (LICENSE_DB_PATH aponta para
 * dentro do disco pago, ex: /data/licenses.json). No plano gratuito isso
 * seria perdido a cada reinício — por isso este projeto exige o plano
 * pago com disco persistente para esta funcionalidade.
 *
 * POLÍTICA DE ATIVAÇÃO: cada chave pode ser ativada em ATÉ 2 MÁQUINAS.
 * A 2ª ativação NÃO reseta a validade — o relógio de 365 dias começa na 1ª.
 * O dono pode liberar as máquinas de uma chave via resetMachine (painel admin).
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DB_PATH = process.env.LICENSE_DB_PATH || path.join(__dirname, 'licenses.json');

/** Quantas máquinas cada licença pode ativar. */
const MAX_ACTIVATIONS = 2;

function ensureDbDir() {
  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function loadDB() {
  ensureDbDir();
  if (!fs.existsSync(DB_PATH)) return { licenses: {} };
  try {
    return JSON.parse(fs.readFileSync(DB_PATH, 'utf8'));
  } catch (e) {
    console.error('Erro ao ler banco de licenças, iniciando um novo:', e);
    return { licenses: {} };
  }
}

function saveDB(db) {
  ensureDbDir();
  fs.writeFileSync(DB_PATH, JSON.stringify(db, null, 2));
}

function generateLicenseKey() {
  const part = () => crypto.randomBytes(2).toString('hex').toUpperCase();
  return `${part()}-${part()}-${part()}-${part()}`;
}

/** Retorna as máquinas vinculadas (compatível com licenças antigas de campo único). */
function getFingerprints(lic) {
  if (Array.isArray(lic.machineFingerprints)) return lic.machineFingerprints;
  if (lic.machineFingerprint) return [lic.machineFingerprint];
  return [];
}

/** Cria uma licença nova (após compra de "instalação nova"). Ainda não está ativada em nenhuma máquina. */
function createLicense(email, orderId) {
  const db = loadDB();
  const key = generateLicenseKey();
  db.licenses[key] = {
    key,
    email: email || null,
    orderId: orderId || null,
    machineFingerprints: [],
    machineNames: [],
    machineFingerprint: null,
    machineName: null,
    activatedAt: null,
    expiresAt: null,
    createdAt: new Date().toISOString(),
    status: 'pending_activation',
  };
  saveDB(db);
  return db.licenses[key];
}

/** Estende a validade de uma licença já existente em +365 dias (renovação). */
function extendLicenseByKey(key, days = 365) {
  const db = loadDB();
  const lic = db.licenses[key];
  if (!lic) return null;
  const base = lic.expiresAt && new Date(lic.expiresAt) > new Date() ? new Date(lic.expiresAt) : new Date();
  base.setDate(base.getDate() + days);
  lic.expiresAt = base.toISOString();
  lic.status = 'active';
  saveDB(db);
  return lic;
}

/** Tenta renovar procurando a licença pelo e-mail do cliente (usado quando não há campo de chave no checkout). */
function extendLicenseByEmail(email, days = 365) {
  const db = loadDB();
  const match = Object.values(db.licenses)
    .filter((l) => l.email && l.email.toLowerCase() === (email || '').toLowerCase())
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))[0];
  if (!match) return null;
  return extendLicenseByKey(match.key, days);
}

/** Ativa uma licença em uma máquina (até MAX_ACTIVATIONS máquinas por chave).
 *  A 2ª ativação NÃO reseta a validade — o relógio de 365 dias começa na 1ª. */
function activateLicense(key, fingerprint, machineName) {
  const db = loadDB();
  const lic = db.licenses[key];
  if (!lic) return { ok: false, reason: 'not_found' };

  const prints = getFingerprints(lic);

  // Já ativada nesta máquina: reativação normal
  if (prints.includes(fingerprint)) {
    return { ok: true, license: lic };
  }

  // Primeira ativação: vincula a máquina e começa os 365 dias
  if (prints.length === 0) {
    lic.machineFingerprints = [fingerprint];
    lic.machineNames = [machineName || null];
    lic.machineFingerprint = fingerprint; // mantido por compatibilidade
    lic.machineName = machineName || null;
    lic.activatedAt = new Date().toISOString();
    if (!lic.expiresAt) {
      const expires = new Date();
      expires.setDate(expires.getDate() + 365);
      lic.expiresAt = expires.toISOString();
    }
    lic.status = 'active';
    saveDB(db);
    return { ok: true, license: lic };
  }

  // Segunda ativação: adiciona a máquina sem mexer na validade
  if (prints.length < MAX_ACTIVATIONS) {
    lic.machineFingerprints = [...prints, fingerprint];
    lic.machineNames = [...(lic.machineNames || [lic.machineName || null]), machineName || null];
    saveDB(db);
    console.log(`[licença] 2ª ativação usada na chave ${key} -> ${machineName || 'máquina sem nome'}`);
    return { ok: true, license: lic, secondActivation: true };
  }

  // Limite de 2 máquinas atingido
  return { ok: false, reason: 'already_activated_elsewhere' };
}

/** Confere se uma licença ainda é válida para determinada máquina. */
function validateLicense(key, fingerprint) {
  const db = loadDB();
  const lic = db.licenses[key];
  if (!lic) return { valid: false, reason: 'not_found' };
  if (!getFingerprints(lic).includes(fingerprint)) return { valid: false, reason: 'wrong_machine' };
  if (!lic.expiresAt || new Date(lic.expiresAt) < new Date()) {
    return { valid: false, reason: 'expired', expiresAt: lic.expiresAt };
  }
  return { valid: true, expiresAt: lic.expiresAt };
}

/** Uso manual pelo dono: libera as máquinas da licença (o cliente reativa depois).
 *  A validade é mantida — o reset não recomeça o relógio de 365 dias. */
function resetMachine(key) {
  const db = loadDB();
  const lic = db.licenses[key];
  if (!lic) return { ok: false, reason: 'not_found' };
  lic.machineFingerprints = [];
  lic.machineNames = [];
  lic.machineFingerprint = null;
  lic.machineName = null;
  saveDB(db);
  return { ok: true, license: lic };
}

function listAllLicenses() {
  const db = loadDB();
  return Object.values(db.licenses).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
}

/** Retorna o banco inteiro, pronto para exportar como arquivo JSON de backup. */
function exportAll() {
  const db = loadDB();
  return {
    exportedAt: new Date().toISOString(),
    licenseCount: Object.keys(db.licenses).length,
    licenses: db.licenses,
  };
}

/**
 * Importa um backup exportado por exportAll(). Faz "merge": adiciona
 * licenças novas e atualiza as existentes com os dados importados (o
 * servidor de origem é considerado a fonte da verdade). NUNCA apaga
 * licenças que só existem localmente — importação é sempre aditiva/segura.
 */
function importLicenses(importedData) {
  if (!importedData || typeof importedData.licenses !== 'object') {
    return { ok: false, reason: 'invalid_format' };
  }

  const db = loadDB();
  let added = 0;
  let updated = 0;

  for (const [key, lic] of Object.entries(importedData.licenses)) {
    if (db.licenses[key]) {
      updated++;
    } else {
      added++;
    }
    db.licenses[key] = lic;
  }

  saveDB(db);
  return { ok: true, added, updated, total: Object.keys(db.licenses).length };
}

module.exports = {
  createLicense,
  extendLicenseByKey,
  extendLicenseByEmail,
  activateLicense,
  validateLicense,
  resetMachine,
  listAllLicenses,
  exportAll,
  importLicenses,
};