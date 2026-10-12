// Credentials and external egress live in this separate container, never in the task container.
const http = require('node:http');
const https = require('node:https');
const fs = require('node:fs');
const crypto = require('node:crypto');

function authFromFile(file) {
  const auth = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (auth.OPENAI_API_KEY) return { base: 'https://api.openai.com/v1', headers: { authorization: `Bearer ${auth.OPENAI_API_KEY}` } };
  const token = auth.tokens?.access_token;
  const account = auth.tokens?.account_id;
  if (!token || !account) throw new Error('Unsupported or missing upstream authentication');
  return { base: 'https://chatgpt.com/backend-api/codex', headers: { authorization: `Bearer ${token}`, 'ChatGPT-Account-ID': account, originator: 'codex_cli_rs' } };
}
function createGateway({ driverToken, loadAuth, model = 'gpt-6-sol', maxBytes = 16 * 1024 * 1024 }) {
  if (!driverToken || driverToken.length < 32) throw new Error('Driver token must contain at least 32 characters');
  const expected = Buffer.from(`Bearer ${driverToken}`);
  return http.createServer(async (req, res) => {
    const received = Buffer.from(req.headers.authorization || '');
    if (received.length !== expected.length || !crypto.timingSafeEqual(received, expected)) { res.writeHead(401); return res.end('Unauthorized'); }
    if (req.method !== 'POST' || !['/v1/responses', '/v1/responses/compact'].includes(req.url)) { res.writeHead(404); return res.end('Route unavailable'); }
    if (req.headers['content-encoding']) { res.writeHead(415); return res.end('Compressed requests disabled'); }
    const chunks = []; let length = 0;
    try {
      for await (const chunk of req) { length += chunk.length; if (length > maxBytes) { res.writeHead(413); res.end('Request too large'); return; } chunks.push(chunk); }
      const body = Buffer.concat(chunks); const payload = JSON.parse(body);
      if (payload.model !== model) { res.writeHead(400); return res.end('Model does not match frozen configuration'); }
      const auth = loadAuth(); const suffix = req.url.slice('/v1'.length); const url = new URL(auth.base + suffix);
      const upstream = (url.protocol === 'https:' ? https : http).request(url, {
        method: 'POST', headers: { ...auth.headers, 'content-type': 'application/json', accept: 'text/event-stream', 'content-length': body.length },
      }, response => {
        res.writeHead(response.statusCode, { 'content-type': response.headers['content-type'] || 'application/json', 'cache-control': 'no-store' });
        response.pipe(res);
      });
      upstream.setTimeout(1800000, () => upstream.destroy(new Error('Upstream timeout')));
      upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('Upstream unavailable'); });
      res.on('close', () => { if (!res.writableEnded) upstream.destroy(); });
      upstream.end(body);
    } catch { if (!res.headersSent) res.writeHead(400); res.end('Invalid request or unavailable authentication'); }
  });
}
module.exports = { createGateway, authFromFile };
if (require.main === module) {
  const token = fs.readFileSync(process.env.BENCHMARK_DRIVER_TOKEN_FILE, 'utf8').trim();
  createGateway({ driverToken: token, loadAuth: () => authFromFile(process.env.UPSTREAM_AUTH_FILE) }).listen(8080, '0.0.0.0');
}
