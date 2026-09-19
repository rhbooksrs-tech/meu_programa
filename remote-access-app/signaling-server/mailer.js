/**
 * Envio de e-mail via Gmail (SMTP com "senha de app").
 *
 * Variáveis de ambiente necessárias (configuradas no Render, aba Environment):
 *   GMAIL_USER  -> seu e-mail do Gmail (ex: seuemail@gmail.com)
 *   GMAIL_APP_PASSWORD -> a "senha de app" gerada nas configurações do Google
 */

const nodemailer = require('nodemailer');

function getTransporter() {
  if (!process.env.GMAIL_USER || !process.env.GMAIL_APP_PASSWORD) {
    console.warn('GMAIL_USER/GMAIL_APP_PASSWORD não configurados — e-mails não serão enviados.');
    return null;
  }
  return nodemailer.createTransport({
    service: 'gmail',
    auth: {
      user: process.env.GMAIL_USER,
      pass: process.env.GMAIL_APP_PASSWORD,
    },
  });
}

async function sendLicenseEmail(toEmail, licenseKey) {
  const transporter = getTransporter();
  if (!transporter || !toEmail) return false;

  try {
    await transporter.sendMail({
      from: `"HennAccess - Suporte" <${process.env.GMAIL_USER}>`,
      to: toEmail,
      subject: 'Sua chave de licença - Acesso Remoto',
      text:
        `Obrigado pela compra!\n\n` +
        `Sua chave de licença é: ${licenseKey}\n\n` +
        `Como usar:\n` +
        `1. Instale o programa no computador.\n` +
        `2. Na primeira vez que abrir, cole essa chave quando for pedida.\n` +
        `3. Pronto — a licença fica ativa por 1 ano a partir da ativação.\n\n` +
        `Guarde este e-mail para futuras renovações.`,
    });
    return true;
  } catch (e) {
    console.error('Erro ao enviar e-mail:', e);
    return false;
  }
}

async function sendRenewalEmail(toEmail, licenseKey, expiresAt) {
  const transporter = getTransporter();
  if (!transporter || !toEmail) return false;

  try {
    await transporter.sendMail({
      from: `"HennAccess - Suporte" <${process.env.GMAIL_USER}>`,
      to: toEmail,
      subject: 'Licença renovada - Acesso Remoto',
      text:
        `Sua licença foi renovada com sucesso!\n\n` +
        `Chave de licença: ${licenseKey}\n` +
        `Nova validade: ${new Date(expiresAt).toLocaleDateString('pt-BR')}\n\n` +
        `Não é necessário reinstalar nada — o programa já está atualizado automaticamente.`,
    });
    return true;
  } catch (e) {
    console.error('Erro ao enviar e-mail de renovação:', e);
    return false;
  }
}

async function sendAdminAlert(subject, text) {
  const transporter = getTransporter();
  const alertTo = process.env.ADMIN_ALERT_EMAIL || process.env.GMAIL_USER;
  if (!transporter || !alertTo) {
    console.warn('Não foi possível enviar alerta administrativo (e-mail não configurado).');
    return false;
  }

  try {
    await transporter.sendMail({
      from: `"HennAccess - Alerta do Sistema" <${process.env.GMAIL_USER}>`,
      to: alertTo,
      subject: `⚠️ ${subject}`,
      text,
    });
    return true;
  } catch (e) {
    console.error('Erro ao enviar alerta administrativo:', e);
    return false;
  }
}

module.exports = { sendLicenseEmail, sendRenewalEmail, sendAdminAlert };
