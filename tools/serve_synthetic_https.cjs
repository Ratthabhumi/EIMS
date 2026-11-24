// Local acceptance only. Use a trusted localhost certificate; never bypass TLS.
const https = require('node:https'), http = require('node:http'), fs = require('node:fs'), crypto = require('node:crypto');
const httpsPort = Number(process.env.EIMS_TEST_HTTPS_PORT || 3449);
const dashboardPort = Number(process.env.EIMS_TEST_DASHBOARD_PORT || 3009);
if (!Number.isInteger(httpsPort) || httpsPort < 1024 || httpsPort > 65535
  || !Number.isInteger(dashboardPort) || dashboardPort < 1024 || dashboardPort > 65535)
  throw Error('Invalid isolated acceptance port configuration');
const pfx = process.env.EIMS_TEST_TLS_PFX, passphrase = process.env.EIMS_TEST_TLS_PASSPHRASE;
const cert = process.env.EIMS_TEST_TLS_CERT, key = process.env.EIMS_TEST_TLS_KEY;
const tlsOptions = pfx ? {pfx: fs.readFileSync(pfx), passphrase} : (cert && key ? {cert: fs.readFileSync(cert), key: fs.readFileSync(key)} : null);
if (!tlsOptions) throw Error('Provide a local PFX or PEM certificate/key outside Git');
const server = https.createServer(tlsOptions, (req, res) => {
  const startedAt = Date.now();
  const requestId = crypto.randomUUID();
  if (![`${'localhost'}:${httpsPort}`, `127.0.0.1:${httpsPort}`].includes(req.headers.host)) {
    res.writeHead(400); res.end('Invalid local host'); return;
  }
  // This loopback proxy is deliberately non-pooled: Next.js closes idle
  // keep-alive sockets, and Node 24's global Agent enables keep-alive by default.
  const upstream = http.request({hostname: '127.0.0.1', port: dashboardPort, method: req.method,
    path: req.url, headers: {...req.headers, 'x-request-id': requestId, 'x-forwarded-proto': 'https', connection: 'close'},
    agent: false, timeout: 65000}, upstreamResponse => {
    const headers = {...upstreamResponse.headers, 'x-request-id': requestId};
    res.writeHead(upstreamResponse.statusCode, headers);
    console.log(JSON.stringify({event:'eims_https_proxy_request',requestId,method:req.method,
      path:new URL(req.url,'https://localhost').pathname,status:upstreamResponse.statusCode,
      durationMs:Date.now()-startedAt}));
    upstreamResponse.pipe(res);
  });
  upstream.on('timeout', () => upstream.destroy(Object.assign(new Error('Dashboard upstream timeout'), {code: 'ETIMEDOUT'})));
  upstream.on('error', error => {
    console.error(JSON.stringify({
      event: 'eims_https_proxy_upstream_failure',
      requestId,
      method: req.method,
      path: new URL(req.url, 'https://localhost').pathname,
      errorName: error.name,
      errorCode: error.code,
      clientAborted: req.aborted === true,
      durationMs: Date.now() - startedAt,
    }));
    if (req.aborted || res.destroyed) return;
    if (!res.headersSent) res.writeHead(502);
    res.end('Local dashboard unavailable');
  });
  req.on('aborted', () => upstream.destroy()); req.pipe(upstream);
});
server.listen(httpsPort, '127.0.0.1', () => console.log(`Synthetic HTTPS: https://localhost:${httpsPort} -> loopback Dashboard ${dashboardPort}`));
