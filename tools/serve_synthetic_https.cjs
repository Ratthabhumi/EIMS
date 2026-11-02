// Local acceptance only. Use a trusted localhost certificate; never bypass TLS.
const https = require('node:https'), http = require('node:http'), fs = require('node:fs');
const cert = process.env.EIMS_TEST_TLS_CERT, key = process.env.EIMS_TEST_TLS_KEY;
if (!cert || !key) throw Error('Provide local certificate/key paths outside Git');
const server = https.createServer({cert: fs.readFileSync(cert), key: fs.readFileSync(key)}, (req, res) => {
  if (!['localhost:3449','127.0.0.1:3449'].includes(req.headers.host)) {
    res.writeHead(400); res.end('Invalid local host'); return;
  }
  const upstream = http.request({hostname: '127.0.0.1', port: 3009, method: req.method,
    path: req.url, headers: {...req.headers, 'x-forwarded-proto': 'https'}, timeout: 65000}, reply => {
    res.writeHead(reply.statusCode, reply.headers); reply.pipe(res);
  });
  upstream.on('timeout', () => upstream.destroy());
  upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('Local dashboard unavailable'); });
  req.on('aborted', () => upstream.destroy()); req.pipe(upstream);
});
server.listen(3449, '127.0.0.1', () => console.log('Synthetic HTTPS: https://localhost:3449 -> loopback Dashboard 3009'));
