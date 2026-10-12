const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { createGateway } = require('./model-gateway.cjs');
const token = 'fixture-driver-token-not-a-credential-000000';
const listen = (server) => new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${server.address().port}`)));
const close = (server) => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); });
test('gateway restricts authentication, routing, model and credential forwarding', async () => {
  let requests = 0;
  const upstream = http.createServer(async (req,res) => {
    requests++; assert.equal(req.headers.authorization,'Bearer fixture-upstream-key');
    assert.equal(req.url,'/v1/responses');
    res.writeHead(200,{'content-type':'text/event-stream'}); res.end('data: fixture-only\n\n');
  });
  const base = await listen(upstream);
  const gateway = createGateway({driverToken:token,loadAuth:()=>({base:base+'/v1',headers:{authorization:'Bearer fixture-upstream-key'}})});
  const url = await listen(gateway);
  const call = (path, body, auth=token, extra={}) => fetch(url+path,{method:'POST',headers:{authorization:'Bearer '+auth,'content-type':'application/json',...extra},body:JSON.stringify(body)});
  try {
    assert.equal((await call('/v1/responses',{model:'gpt-6-sol'},'incorrect')).status,401);
    assert.equal((await call('/v1/other',{model:'gpt-6-sol'})).status,404);
    assert.equal((await call('/v1/responses?target=outside',{model:'gpt-6-sol'})).status,404);
    assert.equal((await call('/v1/responses',{model:'different'})).status,400);
    assert.equal((await call('/v1/responses',{model:'gpt-6-sol'},token,{'content-encoding':'gzip'})).status,415);
    const valid = await call('/v1/responses',{model:'gpt-6-sol',input:'instrumentation fixture'});
    assert.equal(valid.status,200); assert.equal(await valid.text(),'data: fixture-only\n\n'); assert.equal(requests,1);
  } finally { await close(gateway); await close(upstream); }
});
