/**
 * Autenticação HTTP Basic simples, sem dependências externas.
 * Usada para proteger o painel /admin com usuário e senha.
 */

module.exports = function basicAuth({ user, password }) {
  return function (req, res, next) {
    const header = req.headers.authorization;
    if (!header || !header.startsWith('Basic ')) {
      res.set('WWW-Authenticate', 'Basic realm="Admin"');
      return res.status(401).send('Autenticação necessária.');
    }
    const decoded = Buffer.from(header.slice(6), 'base64').toString('utf8');
    const [reqUser, reqPassword] = decoded.split(':');
    if (reqUser === user && reqPassword === password) {
      return next();
    }
    res.set('WWW-Authenticate', 'Basic realm="Admin"');
    return res.status(401).send('Usuário ou senha incorretos.');
  };
};
