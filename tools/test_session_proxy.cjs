// No listener/browser/model needed. Executes actual compiled Next route handlers.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {createRequire}=require('module');
const loginCredential=process.env.EIMS_TEST_LOGIN_CREDENTIAL;
const dashboard=path.resolve('clients/dashboard');
const req=createRequire(path.join(dashboard,'package.json'));
const ts=req('typescript'),{NextRequest}=req('next/server');
function load(file,aliases={}){
 const mod={exports:{}};const code=ts.transpileModule(fs.readFileSync(path.join(dashboard,'src',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 new Function('require','module','exports',code)(id=>aliases[id]||req(id),mod,mod.exports);return mod.exports;
}
const helper=load('lib/session-proxy.ts'),gate=load('lib/login-gate.ts');const aliases={'@/lib/session-proxy':helper,'@/lib/login-gate':gate};
const login=load('app/api/session/login/route.ts',aliases),logout=load('app/api/session/logout/route.ts',aliases),proxy=load('app/api/eims/[...path]/route.ts',aliases);
function request(route,method='GET',body,headers={},base='https://localhost:3449'){
 return new NextRequest(base+route,{method,headers:{...(method==='GET'?{}:{origin:base,'content-type':'application/json'}),...headers},body:body===undefined?undefined:JSON.stringify(body)});
}
(async()=>{
 const live=process.argv.includes('--live');let tests=0;const results={boundary:live?'Next handlers -> real loopback HTTP login/JWT/PostgreSQL; no Next HTTP/browser':'Next handlers with synthetic upstream; no auth certification',tests:[]};
 const check=(name)=>{tests++;results.tests.push({name,status:'PASS'})};
 if(live){
  process.env.EIMS_BACKEND_URL='http://127.0.0.1:8019';
  const r=await login.POST(request('/api/session/login','POST',{username:'synthetic-browser-review',password:loginCredential}));
  assert.equal(r.status,200);assert.deepEqual(await r.json(),{authenticated:true});
  const cookie=r.cookies.get('eims_session');assert(cookie?.value);assert(r.headers.get('set-cookie').includes('HttpOnly'));assert(r.headers.get('set-cookie').includes('Secure'));check('real credential login issues HttpOnly Secure session; no JWT response');
  const c={cookie:'eims_session='+cookie.value};
  const session=await proxy.GET(request('/api/eims/api/v1/auth/session','GET',undefined,c),{params:Promise.resolve({path:['api','v1','auth','session']})});
  assert.equal(session.status,200);assert.equal((await session.json()).username,'synthetic-browser-review');check('cookie forwarded server-side and verified against real account');
  const signout=await logout.POST(request('/api/session/logout','POST',{},c));assert(signout.headers.get('set-cookie').includes('Max-Age=0'));check('logout expires browser cookie');
  const copied=await proxy.GET(request('/api/eims/api/v1/auth/session','GET',undefined,c),{params:Promise.resolve({path:['api','v1','auth','session']})});assert.equal(copied.status,401);check('copied pre-logout JWT is revoked server-side');
  const denied=await proxy.GET(request('/api/eims/api/v1/history'),{params:Promise.resolve({path:['api','v1','history']})});assert.equal(denied.status,401);check('protected request without logged-out cookie is rejected');
  const expired=await login.POST(request('/api/session/login','POST',{username:'synthetic-expiry',password:loginCredential}));assert.equal(expired.status,200);
  const ec=expired.cookies.get('eims_session').value;await new Promise(r=>setTimeout(r,3500));
  const stale=await proxy.GET(request('/api/eims/api/v1/auth/session','GET',undefined,{cookie:'eims_session='+ec}),{params:Promise.resolve({path:['api','v1','auth','session']})});assert.equal(stale.status,401);assert(stale.headers.get('set-cookie').includes('Max-Age=0'));check('real login-issued expired JWT rejected and cookie cleared');
 }else{
  const original=global.fetch;let captured;
  const token='unit.'+Buffer.from(JSON.stringify({exp:Math.floor(Date.now()/1000)+60})).toString('base64url')+'.unit';
  global.fetch=async(url,init)=>{captured={url,init};return new Response(JSON.stringify({access_token:token}),{headers:{'content-type':'application/json'}})};
  const good=await login.POST(request('/api/session/login','POST',{username:'synthetic',password:'synthetic-only'}));assert.equal(good.status,200);assert(!(await good.text()).includes(token));assert.match(good.headers.get('set-cookie'),/HttpOnly/);assert.match(good.headers.get('set-cookie'),/Secure/);assert.match(good.headers.get('set-cookie'),/SameSite=strict/i);check('login token remains HttpOnly Secure SameSite Strict and out of JSON');
  assert.equal((await login.POST(request('/api/session/login','POST',{}, {origin:'https://other.invalid'}))).status,403);check('login CSRF rejected');
  assert.equal((await logout.POST(request('/api/session/logout','POST',{}, {origin:'https://other.invalid'}))).status,403);check('logout CSRF rejected');
  assert.equal((await login.POST(request('/api/session/login','POST',{}, {origin:''}))).status,403);
  process.env.EIMS_DASHBOARD_ORIGIN='https://localhost:3449';
  assert.equal((await login.POST(request('/api/session/login','POST',{}, {},'https://forged.invalid'))).status,403);
  assert.equal(helper.sameOrigin(request('/x','POST',{}, {host:'forged.invalid','x-forwarded-host':'forged.invalid','x-forwarded-proto':'http'})),true);
  delete process.env.EIMS_DASHBOARD_ORIGIN;check('missing/conflicting origin rejected; forwarded host cannot replace pinned origin');
  const ctx={params:Promise.resolve({path:['api','v1','history']})};
  assert.equal((await proxy.POST(request('/api/eims/api/v1/history','POST',{}, {origin:'https://other.invalid'}),ctx)).status,403);check('API mutation CSRF rejected');
  await proxy.GET(request('/api/eims/api/v1/history','GET',undefined,{cookie:'eims_session=synthetic-cookie',authorization:'Bearer must-not-forward'}),ctx);
  assert.equal(captured.init.headers.get('authorization'),'Bearer synthetic-cookie');assert.equal(captured.init.headers.get('cookie'),null);assert.equal(captured.init.redirect,'error');assert.equal(captured.init.headers.get('connection'),'close');assert.equal(captured.init.cache,'no-store');assert(captured.init.signal instanceof AbortSignal);assert.match(captured.url,/\/api\/v1\/history\/$/);check('proxy uses cookie-only identity, strips browser headers and prevents redirects');
  assert.equal((await proxy.GET(request('/api/eims/api/v1/auth/login'),{params:Promise.resolve({path:['api','v1','auth','login']})})).status,404);check('raw token-issuing login path not exposed through generic proxy');
  for(const segment of ['auth/login','auth%2Flogin','..','\\auth'])assert.equal((await proxy.GET(request('/api/eims/api/v1/x'),{params:Promise.resolve({path:['api','v1',segment]})})).status,404);check('encoded separators cannot bypass token endpoint restriction');
  global.fetch=async()=>new Response('private traceback synthetic-only',{status:500});const fail=await proxy.GET(request('/api/eims/api/v1/history'),ctx);assert.equal(fail.status,502);assert(!(await fail.text()).includes('traceback'));check('upstream server error details withheld');
  global.fetch=async()=>new Response('{}',{status:401});const invalid=await proxy.GET(request('/api/eims/api/v1/history'),ctx);assert.match(invalid.headers.get('set-cookie'),/Max-Age=0/);check('401 expires stale session');
  { // Observed 502 condition: session probe whose upstream keep-alive socket is dropped before any response bytes.
    const sctx={params:Promise.resolve({path:['api','v1','auth','session']})},secret='secret.session.token';
    const logs=[],origErr=console.error;console.error=(...a)=>logs.push(a.join(' '));
    const probe=()=>proxy.GET(request('/api/eims/api/v1/auth/session?probe=private-query','GET',undefined,{cookie:'eims_session='+secret,authorization:'Bearer browser-secret'}),sctx);
    try{
      const socketError=Object.assign(new TypeError('fetch failed'),{cause:Object.assign(new Error('other side closed'),{code:'UND_ERR_SOCKET'})});
      global.fetch=async()=>{throw socketError};
      const dropped=await probe();assert.equal(dropped.status,502);assert.deepEqual(await dropped.json(),{detail:'Analysis service unavailable'});assert.equal(dropped.headers.get('set-cookie'),null);
      const entry=JSON.parse(logs.pop());assert.equal(entry.event,'eims_bff_upstream_failure');assert.equal(entry.method,'GET');assert.equal(entry.path,'/api/eims/api/v1/auth/session');
      assert.equal(entry.errorName,'TypeError');assert.equal(entry.errorCode,'UND_ERR_SOCKET');assert.equal(entry.clientAborted,false);assert.equal(typeof entry.durationMs,'number');
      const raw=JSON.stringify(entry);assert(!raw.includes(secret)&&!raw.includes('browser-secret')&&!raw.includes('private-query'));
      check('dropped upstream socket fails closed as 502 with secret-free diagnostic');
      const ac=new AbortController();const abortedReq=new NextRequest('https://localhost:3449/api/eims/api/v1/auth/session',{method:'GET',signal:ac.signal});ac.abort();
      global.fetch=async()=>{throw Object.assign(new Error('This operation was aborted'),{name:'AbortError'})};
      const aborted=await proxy.GET(abortedReq,sctx);assert.equal(aborted.status,502);
      const abortEntry=JSON.parse(logs.pop());assert.equal(abortEntry.errorName,'AbortError');assert.equal(abortEntry.clientAborted,true);check('client abort is distinguishable in diagnostics and never converted to success');
      global.fetch=async()=>new Response('private traceback',{status:503});const unavailable=await probe();assert.equal(unavailable.status,502);
      const statusEntry=JSON.parse(logs.pop());assert.equal(statusEntry.upstreamStatus,503);assert.equal(statusEntry.errorCode,undefined);check('upstream 5xx logged by status without body or headers');
      global.fetch=async()=>new Response('{}',{status:401});assert.equal((await probe()).status,401);assert.equal(logs.length,0);check('auth expiry 401 stays 401 and emits no failure diagnostic');
    }finally{console.error=origErr;}
    // Real sockets, no mocked fetch.
    global.fetch=original;const net=require('net'),http=require('http');
    const priorBackend=process.env.EIMS_BACKEND_URL;const quiet=console.error;console.error=()=>{};
    const listen=srv=>new Promise(r=>srv.listen(0,'127.0.0.1',r));
    try{
      // Real HTTP server: two sequential requests across an idle gap longer than the server keep-alive window must use separate sockets and both succeed.
      const sockets=new Set(),seen=[];
      const ok=http.createServer((rq,rs)=>{seen.push(rq.headers.connection);rs.setHeader('content-type','application/json');rs.end('{}')});
      ok.keepAliveTimeout=5000;ok.on('connection',s=>sockets.add(s));await listen(ok);
      process.env.EIMS_BACKEND_URL='http://127.0.0.1:'+ok.address().port;
      assert.equal((await probe()).status,200);await new Promise(r=>setTimeout(r,5500));assert.equal((await probe()).status,200);
      assert.equal(sockets.size,2);assert.deepEqual(seen,['close','close']);
      ok.close();check('sequential requests across >5s idle gap use separate sockets (Connection: close) and both succeed');
      // Dropped connection: exactly one attempt, 502, no retry.
      let conns=0;const dropper=net.createServer(s=>{conns++;s.on('error',()=>{});s.on('data',()=>s.destroy())});await listen(dropper);
      process.env.EIMS_BACKEND_URL='http://127.0.0.1:'+dropper.address().port;
      assert.equal((await probe()).status,502);assert.equal(conns,1);dropper.close();check('upstream socket reset returns 502 with exactly one upstream attempt (no retry)');
      const refused=net.createServer();await listen(refused);const port=refused.address().port;await new Promise(r=>refused.close(r));
      process.env.EIMS_BACKEND_URL='http://127.0.0.1:'+port;assert.equal((await probe()).status,502);check('true upstream outage (connection refused) still returns 502');
    }finally{console.error=quiet;if(priorBackend===undefined)delete process.env.EIMS_BACKEND_URL;else process.env.EIMS_BACKEND_URL=priorBackend;}
  }
  global.fetch=async()=>{throw Error('synthetic network failure')};
  const retryLogout=await logout.POST(request('/api/session/logout','POST',{}, {cookie:'eims_session=synthetic-cookie'}));
  assert.equal(retryLogout.status,502);assert.equal(retryLogout.headers.get('set-cookie'),null);check('failed revocation retains cookie and asks for retry');
  global.fetch=async()=>new Response('{}',{status:200});
  const revoked=await logout.POST(request('/api/session/logout','POST',{}, {cookie:'eims_session=synthetic-cookie'}));
  assert.match(revoked.headers.get('set-cookie'),/Max-Age=0/);assert.equal(revoked.headers.get('cache-control'),'no-store');check('successful backend revocation clears cookie with no-store response');
  await assert.rejects(helper.boundedBody(request('/x','POST',{long:'synthetic'}),3),/BODY_TOO_LARGE/);check('stream body bound enforced');
  process.env.EIMS_ALLOW_INSECURE_LOCAL_SESSION='1';assert.equal(helper.cookieOptions(request('/x','GET',undefined,{},'http://localhost:3009')).secure,false);assert.equal(helper.cookieOptions(request('/x','GET',undefined,{},'http://remote.invalid')).secure,true);delete process.env.EIMS_ALLOW_INSECURE_LOCAL_SESSION;check('insecure cookie opt-in restricted to explicit loopback HTTP');
  global.fetch=original;
  let now=100000;const limiter=new gate.LoginGate(()=>now);
  assert.deepEqual(Array.from({length:8},()=>limiter.reserve('synthetic')),Array(8).fill(0));assert(limiter.reserve('synthetic')>0);now+=60001;assert.equal(limiter.reserve('synthetic'),0);check('bounded login window recovers without permanent account lockout');
  global.fetch=async()=>{captured=(captured||0)+1;return new Response('{}',{status:401})};captured=0;
  const burst=await Promise.all(Array.from({length:20},()=>login.POST(request('/api/session/login','POST',{username:'parallel-control',password:'synthetic-only'}))));
  assert.equal(captured,8);assert.equal(burst.filter(r=>r.status===429).length,12);check('parallel BFF attempts cap actual upstream requests');
  global.fetch=original;
  const {escapeReportData}=load('lib/report-data.ts');
  const payload='<img src=x onerror="window.syntheticOnly=true">';
  async function renderPdf(source,file){
    const parsed=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let arrow;
    function find(n){if(ts.isVariableDeclaration(n)&&n.name.getText(parsed)==='downloadPDF')arrow=n.initializer.getText(parsed);ts.forEachChild(n,find)}find(parsed);
    assert(arrow);const code=ts.transpileModule('module.exports = '+arrow,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
    let html='';const document={createElement:()=>({style:{},set innerHTML(value){html=value}}),body:{appendChild(){},removeChild(){}}};
    class PDF {constructor(){this.internal={pageSize:{getWidth:()=>210,getHeight:()=>297}}}addImage(){}addPage(){}save(){}}
    const dependencies=id=>({__esModule:true,default:id==='jspdf'?PDF:async()=>({width:794,height:1100,toDataURL:()=>''})});
    const model={eventId:payload,provider:payload,eventMetadata:{logName:payload},solutionSummary:{overview:payload,evidence:[payload],steps:[payload],causes:[payload]},searchResults:[{title:payload,link:payload,snippet:payload}]};
    const mod={exports:{}};
    new Function('module','exports','require','result','toast','document','friendlyLabel','catalogMap','escapeReportData','isSyntheticDemo',code)(mod,mod.exports,dependencies,model,{loading(){},success(){},error(e){throw Error(String(e))}},document,x=>({title:x.eventId,provider:x.provider}),new Map(),escapeReportData,x=>String(x?.eventId??'').toUpperCase()==='AINC-2026-0910-0001');
    await mod.exports(model);return html;
  }
  for(const file of ['src/app/analyzer/page.tsx','src/components/AnalyzerHistoryList.tsx']){
    const baseline=require('child_process').execFileSync('git',['show','443676b:clients/dashboard/'+file],{encoding:'utf8'});
    assert((await renderPdf(baseline,file)).includes('<img src=x')); // reproduction, no DOM execution
    const safe=await renderPdf(fs.readFileSync(path.join(dashboard,file),'utf8'),file);
    assert(!safe.includes('<img src=x'));assert(safe.includes('&lt;img'));check('actual '+file+' PDF template escapes injection that reproduced in PR4');
  }
 }
 results.passed=tests;fs.mkdirSync('test-results',{recursive:true});fs.writeFileSync('test-results/session-proxy-'+(live?'live':'unit')+'.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exit(1)});
