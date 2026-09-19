/**
 * Script de importação de backup - roda no servidor CÓPIA (fora do Render).
 *
 * Uso:
 *   node import-licenses.js caminho/para/henndesk_backup_XXXXX.json
 *
 * O que faz:
 *   - Lê o arquivo de backup exportado do painel admin do servidor principal
 *   - Adiciona licenças novas e atualiza as que já existem localmente
 *   - NUNCA apaga nada que só exista no servidor cópia (importação é segura,
 *     só soma/atualiza, nunca remove)
 *
 * Recomendação: rode esse comando periodicamente (ex: uma vez por dia, via
 * tarefa agendada/cron) para manter o servidor cópia sempre sincronizado
 * com o principal.
 */

const fs = require('fs');
const path = require('path');
const license = require('./license');

const filePath = process.argv[2];

if (!filePath) {
  console.error('Uso: node import-licenses.js caminho/para/arquivo_de_backup.json');
  process.exit(1);
}

if (!fs.existsSync(filePath)) {
  console.error(`Arquivo não encontrado: ${filePath}`);
  process.exit(1);
}

try {
  const raw = fs.readFileSync(filePath, 'utf8');
  const data = JSON.parse(raw);

  console.log(`Importando backup de ${data.exportedAt || 'data desconhecida'}...`);
  console.log(`Licenças no arquivo: ${data.licenseCount ?? Object.keys(data.licenses || {}).length}`);

  const result = license.importLicenses(data);

  if (!result.ok) {
    console.error('Falha na importação:', result.reason);
    process.exit(1);
  }

  console.log(`\n✅ Importação concluída:`);
  console.log(`   Novas licenças adicionadas: ${result.added}`);
  console.log(`   Licenças já existentes atualizadas: ${result.updated}`);
  console.log(`   Total de licenças agora neste servidor: ${result.total}`);
} catch (e) {
  console.error('Erro ao processar o arquivo de backup:', e.message);
  process.exit(1);
}
