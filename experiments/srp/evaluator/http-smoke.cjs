const assert = require('node:assert/strict');
(async () => {
  const base = process.env.BENCHMARK_API_URL || 'http://localhost:3170';
  const get = async path => { const r=await fetch(base+path,{signal:AbortSignal.timeout(10000)});return {status:r.status,body:await r.text()}; };
  const ping=await get('/ping'); assert.deepEqual(ping,{status:200,body:'Success'});
  const health=await get('/health'); assert.equal(health.status,200); assert.equal(JSON.parse(health.body).info.database.status,'up');
  const blocked=await get('/v1/team-collection/search/team-a?searchQuery=x&take=10&skip=0');assert.equal(blocked.status,403);assert.equal(JSON.parse(blocked.body).message,'auth/cookies_not_found');
  const missing=await get('/');assert.equal(missing.status,404);
  console.log(JSON.stringify({ping,health:JSON.parse(health.body),unauthenticatedSearch:JSON.parse(blocked.body),missingRootStatus:missing.status}));
})().catch(error=>{console.error(error.message);process.exitCode=1;});
