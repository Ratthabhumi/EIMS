// No listener/browser/model needed. Executes actual compiled Next route handlers.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {createRequire}=require('module');
const dashboard=path.resolve('clients/dashboard');
const req=createRequire(path.join(dashboard,'package.json'));
const ts=req('typescript'),{NextRequest}=req('next/server');
function load(file,aliases={}){
 const mod={exports:{}};const code=ts.transpileModule(fs.readFileSync(path.join(dashboard,'src',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 new Function('require','module','exports',code)(id=>aliases[id]||req(id),mod,mod.exports);return mod.exports;
}
const helper=load('lib/session-proxy.ts');const aliases={'@/lib/session-proxy':helper};
const login=load('app/api/session/login/route.ts',aliases),logout=load('app/api/session/logout/route.ts',aliases),proxy=load('app/api/eims/[...path]/route.ts',aliases);
function request(route,method='GET',body,headers={},base='https://localhost:3449'){
 return new NextRequest(base+route,{method,headers:{...(method==='GET'?{}:{origin:base,'content-type':'application/json'}),...headers},body:body===undefined?undefined:JSON.stringify(body)});
}
(async()=>{
 const live=process.argv.includes('--live');let tests=0;const results={boundary:live?'Next handlers -> real loopback HTTP login/JWT/PostgreSQL; no Next HTTP/browser':'Next handlers with synthetic upstream; no auth certification',tests:[]};
 const check=(name)=>{tests++;results.tests.push({name,status:'PASS'})};
 if(live){
  process.env.EIMS_BACKEND_URL='http://127.0.0.1:8019';
  const r=await login.POST(request('/api/session/login','POST',{username:'synthetic-browser-review',password:'synthetic-test-password-only'}));
  assert.equal(r.status,200);assert.deepEqual(await r.json(),{authenticated:true});
  const cookie=r.cookies.get('eims_session');assert(cookie?.value);assert(r.headers.get('set-cookie').includes('HttpOnly'));assert(r.headers.get('set-cookie').includes('Secure'));check('real credential login issues HttpOnly Secure session; no JWT response');
  const c={cookie:'eims_session='+cookie.value};
  const session=await proxy.GET(request('/api/eims/api/v1/auth/session','GET',undefined,c),{params:Promise.resolve({path:['api','v1','auth','session']})});
  assert.equal(session.status,200);assert.equal((await session.json()).username,'synthetic-browser-review');check('cookie forwarded server-side and verified against real account');
  const signout=await logout.POST(request('/api/session/logout','POST',{},c));assert(signout.headers.get('set-cookie').includes('Max-Age=0'));check('logout expires browser cookie');
  const denied=await proxy.GET(request('/api/eims/api/v1/history'),{params:Promise.resolve({path:['api','v1','history']})});assert.equal(denied.status,401);check('protected request without logged-out cookie is rejected');
  const expired=await login.POST(request('/api/session/login','POST',{username:'synthetic-expiry',password:'synthetic-test-password-only'}));assert.equal(expired.status,200);
  const ec=expired.cookies.get('eims_session').value;await new Promise(r=>setTimeout(r,3500));
  const stale=await proxy.GET(request('/api/eims/api/v1/auth/session','GET',undefined,{cookie:'eims_session='+ec}),{params:Promise.resolve({path:['api','v1','auth','session']})});assert.equal(stale.status,401);assert(stale.headers.get('set-cookie').includes('Max-Age=0'));check('real login-issued expired JWT rejected and cookie cleared');
 }else{
  const original=global.fetch;let captured;
  const token='unit.'+Buffer.from(JSON.stringify({exp:Math.floor(Date.now()/1000)+60})).toString('base64url')+'.unit';
  global.fetch=async(url,init)=>{captured={url,init};return new Response(JSON.stringify({access_token:token}),{headers:{'content-type':'application/json'}})};
  const good=await login.POST(request('/api/session/login','POST',{username:'synthetic',password:'synthetic-only'}));assert.equal(good.status,200);assert(!(await good.text()).includes(token));assert.match(good.headers.get('set-cookie'),/HttpOnly/);assert.match(good.headers.get('set-cookie'),/Secure/);assert.match(good.headers.get('set-cookie'),/SameSite=strict/i);check('login token remains HttpOnly Secure SameSite Strict and out of JSON');
  assert.equal((await login.POST(request('/api/session/login','POST',{}, {origin:'https://other.invalid'}))).status,403);check('login CSRF rejected');
  assert.equal((await logout.POST(request('/api/session/logout','POST',{}, {origin:'https://other.invalid'}))).status,403);check('logout CSRF rejected');
  const ctx={params:Promise.resolve({path:['api','v1','history']})};
  assert.equal((await proxy.POST(request('/api/eims/api/v1/history','POST',{}, {origin:'https://other.invalid'}),ctx)).status,403);check('API mutation CSRF rejected');
  await proxy.GET(request('/api/eims/api/v1/history','GET',undefined,{cookie:'eims_session=synthetic-cookie',authorization:'Bearer must-not-forward'}),ctx);
  assert.equal(captured.init.headers.get('authorization'),'Bearer synthetic-cookie');assert.equal(captured.init.headers.get('cookie'),null);assert.equal(captured.init.redirect,'error');assert.match(captured.url,/\/api\/v1\/history\/$/);check('proxy uses cookie-only identity, strips browser headers and prevents redirects');
  assert.equal((await proxy.GET(request('/api/eims/api/v1/auth/login'),{params:Promise.resolve({path:['api','v1','auth','login']})})).status,404);check('raw token-issuing login path not exposed through generic proxy');
  for(const segment of ['auth/login','auth%2Flogin','..','\\auth'])assert.equal((await proxy.GET(request('/api/eims/api/v1/x'),{params:Promise.resolve({path:['api','v1',segment]})})).status,404);check('encoded separators cannot bypass token endpoint restriction');
  global.fetch=async()=>new Response('private traceback synthetic-only',{status:500});const fail=await proxy.GET(request('/api/eims/api/v1/history'),ctx);assert.equal(fail.status,502);assert(!(await fail.text()).includes('traceback'));check('upstream server error details withheld');
  global.fetch=async()=>new Response('{}',{status:401});const invalid=await proxy.GET(request('/api/eims/api/v1/history'),ctx);assert.match(invalid.headers.get('set-cookie'),/Max-Age=0/);check('401 expires stale session');
  await assert.rejects(helper.boundedBody(request('/x','POST',{long:'synthetic'}),3),/BODY_TOO_LARGE/);check('stream body bound enforced');
  process.env.EIMS_ALLOW_INSECURE_LOCAL_SESSION='1';assert.equal(helper.cookieOptions(request('/x','GET',undefined,{},'http://localhost:3009')).secure,false);assert.equal(helper.cookieOptions(request('/x','GET',undefined,{},'http://remote.invalid')).secure,true);delete process.env.EIMS_ALLOW_INSECURE_LOCAL_SESSION;check('insecure cookie opt-in restricted to explicit loopback HTTP');
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
    new Function('module','exports','require','result','toast','document','friendlyLabel','catalogMap','escapeReportData',code)(mod,mod.exports,dependencies,model,{loading(){},success(){},error(e){throw Error(String(e))}},document,x=>({title:x.eventId,provider:x.provider}),new Map(),escapeReportData);
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
