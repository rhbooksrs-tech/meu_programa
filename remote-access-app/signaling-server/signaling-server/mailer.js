/**
 * Envio de e-mail via Gmail (SMTP com "senha de app").
 *
 * Variáveis de ambiente necessárias (configuradas no Render, aba Environment):
 *   GMAIL_USER  -> seu e-mail do Gmail (ex: seuemail@gmail.com)
 *   GMAIL_APP_PASSWORD -> a "senha de app" gerada nas configurações do Google
 *   APP_DOWNLOAD_URL -> link público do executável (o mesmo usado pelo atualizador)
 */

const nodemailer = require('nodemailer');
const path = require('path'); // ✅ NOVO: para localizar o PDF na pasta do projeto

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

// ✅ NOVO: caminho do PDF (o arquivo precisa estar na MESMA pasta deste mailer.js)
const GUIDE_PDF = path.join(__dirname, 'Guia de Instalação - HennAccess.pdf');

async function sendLicenseEmail(toEmail, licenseKey) {
  const transporter = getTransporter();
  if (!transporter || !toEmail) return false;

  // Link de download vem da mesma variável usada pelo atualizador do app
  const downloadUrl = process.env.PUBLIC_DOWNLOAD_URL || process.env.APP_DOWNLOAD_URL || '';
  const downloadBlock = downloadUrl
    ? `Baixe o programa aqui:\n${downloadUrl}\n\n`
    : '';

  const divider = '\n\n' + '─'.repeat(48) + '\n\n';

  try {
    await transporter.sendMail({
      from: `"HennAccess - Suporte" <${process.env.GMAIL_USER}>`,
      to: toEmail,
      subject: 'Sua chave de licença - HennAccess | Your license key | Su clave de licencia',
      text:
        // ---------- PORTUGUÊS ----------
        `Obrigado pela compra!\n\n` +
        `Sua chave de licença é: ${licenseKey}\n\n` +
        downloadBlock +
        `Como usar:\n` +
        `1. Baixe e instale o programa no computador (Windows).\n` +
        `2. Na primeira vez que abrir, cole essa chave quando for pedida.\n` +
        `3. Pronto — a licença fica ativa por 1 ano a partir da ativação.\n\n` +
        `Sua chave pode ser ativada em até 2 computadores.\n\n` +
        `⚠️ IMPORTANTE: o HennAccess funciona apenas no Windows 10 e 11 (64 bits).\n` +
        `Não funciona em versões de 32 bits do Windows.\n\n` +
        `📄 Guia de instalação completo em anexo: Guia de Instalação - HennAccess.pdf\n\n` +
        `Dúvidas? Responda este e-mail — o suporte é direto com o desenvolvedor.\n\n` +
        `Guarde este e-mail para futuras renovações.` +

        divider +

        // ---------- ENGLISH ----------
        `Thank you for your purchase!\n\n` +
        `Your license key is: ${licenseKey}\n\n` +
        (downloadUrl ? `Download the program here:\n${downloadUrl}\n\n` : '') +
        `How to use:\n` +
        `1. Download and install the program on your computer (Windows).\n` +
        `2. The first time you open it, paste this key when prompted.\n` +
        `3. Done — the license stays active for 1 year from activation.\n\n` +
        `Your key can be activated on up to 2 computers.\n\n` +
        `⚠️ IMPORTANT: HennAccess works only on Windows 10 and 11 (64-bit).\n` +
        `It does not work on 32-bit versions of Windows.\n\n` +
        `📄 Full installation guide attached: HennAccess Installation Guide.pdf\n\n` +
        `Questions? Just reply to this email — support is direct with the developer.\n\n` +
        `Keep this email for future renewals.` +

        divider +

        // ---------- ESPAÑOL ----------
        `¡Gracias por tu compra!\n\n` +
        `Tu clave de licencia es: ${licenseKey}\n\n` +
        (downloadUrl ? `Descarga el programa aquí:\n${downloadUrl}\n\n` : '') +
        `Cómo usar:\n` +
        `1. Descarga e instala el programa en la computadora (Windows).\n` +
        `2. La primera vez que lo abras, pega esta clave cuando se te solicite.\n` +
        `3. Listo — la licencia permanece activa por 1 año desde la activación.\n\n` +
        `Tu clave puede activarse en hasta 2 computadoras.\n\n` +
        `⚠️ IMPORTANTE: HennAccess funciona solo en Windows 10 y 11 (64 bits).\n` +
        `No funciona en versiones de 32 bits de Windows.\n\n` +
        `📄 Guía de instalación completa adjunta: Guía de Instalación - HennAccess.pdf\n\n` +
        `¿Dudas? Responde este correo — el soporte es directo con el desarrollador.\n\n` +
        `Guarda este correo para futuras renovaciones.`,
      attachments: [
        {
          filename: 'Guia de Instalação - HennAccess.pdf',
          path: GUIDE_PDF_PT,
          contentType: 'application/pdf',
        },
        {
          filename: 'HennAccess Installation Guide.pdf',
          path: GUIDE_PDF_EN,
          contentType: 'application/pdf',
        },
        {
          filename: 'Guía de Instalación - HennAccess.pdf',
          path: GUIDE_PDF_ES,
          contentType: 'application/pdf',
        },
      ],
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

  const validade = new Date(expiresAt).toLocaleDateString('pt-BR');
  const divider = '\n\n' + '─'.repeat(48) + '\n\n';

  try {
    await transporter.sendMail({
      from: `"HennAccess - Suporte" <${process.env.GMAIL_USER}>`,
      to: toEmail,
      subject: 'Licença renovada - HennAccess | License renewed | Licencia renovada',
      text:
        // ---------- PORTUGUÊS ----------
        `Sua licença foi renovada com sucesso!\n\n` +
        `Chave de licença: ${licenseKey}\n` +
        `Nova validade: ${validade}\n\n` +
        `Não é necessário reinstalar nada — o programa já é atualizado automaticamente.` +

        divider +

        // ---------- ENGLISH ----------
        `Your license has been renewed successfully!\n\n` +
        `License key: ${licenseKey}\n` +
        `New expiration date: ${validade}\n\n` +
        `No need to reinstall anything — the program updates itself automatically.` +

        divider +

        // ---------- ESPAÑOL ----------
        `¡Tu licencia se renovó con éxito!\n\n` +
        `Clave de licencia: ${licenseKey}\n` +
        `Nueva validez: ${validade}\n\n` +
        `No es necesario reinstalar nada — el programa se actualiza automáticamente.`,
    });
    return true;
  } catch (e) {
    console.error('Erro ao enviar e-mail de renovação:', e);
    return false;
  }
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