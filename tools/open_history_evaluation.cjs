/* Participant browser only. Start the guarded SQLite API and UI preview first.
 * Real responses are forwarded; no operational browser/profile is reused.
 */
let pw;
try {
 pw=require(process.env.EIMS_PLAYWRIGHT_MODULE || 'playwright');
} catch {
 const path=require('node:path');
 const fallback=path.join(process.env.USERPROFILE || '', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
 pw=require(fallback);
}
const {chromium,request}=pw;
const assert=require('node:assert/strict');
const ui='http://127.0.0.1:3115',api='http://127.0.0.1:3116';
async function openEvaluation({headless=false}={}) {
 const probe=await request.newContext();
 try {
  const response=await probe.get(api+'/__sandbox');
  assert.deepEqual(await response.json(),{purpose:'synthetic-history-only',dialect:'sqlite',operational_startup:false});
 } finally {await probe.dispose()}
 const launchArgs=[];
 if(headless) launchArgs.push('--headless=new');
 const browser=await chromium.launch({headless,channel:process.env.EIMS_UI_BROWSER || 'msedge',args:launchArgs});
 let closing=false;
 try {
  const context=await browser.newContext();
  await context.route('**/*',async route=>{
   try {
    const raw=route.request().url();
    if(raw.startsWith('blob:') || raw.startsWith('data:')){
     return route.continue().catch(()=>{});
    }
    const url=new URL(raw);
    if(url.pathname.startsWith('/api/')){
     return route.continue({url:api+url.pathname+url.search}).catch(()=>{});
    }
    if(url.origin===ui)return route.continue().catch(()=>{});
    return route.abort().catch(()=>{});
   }catch(error){
    if(!closing && process.env.DEBUG)console.warn('[route warning]',error.message);
   }
  });
  const page=await context.newPage();
  page.once('close',()=>{closing=true});
  await page.goto(ui+'/analyzer',{waitUntil:'networkidle',timeout:90000});
  const close=async()=>{
   closing=true;
   // Keep routing installed until the context is closed; no request can
   // fall back to the UI's operational default API during teardown.
   try {await context.close()}finally{await browser.close()}
  };
  return {browser,context,page,close};
 }catch(error){closing=true;await browser.close();throw error}
}
module.exports={openEvaluation};
if(require.main===module) {
 (async()=>{
  const {page,close}=await openEvaluation();
  try {
   console.log('Synthetic evaluation browser ready. All API calls go to isolated SQLite. No participant metrics are recorded automatically. Close this window to finish.');
   await new Promise(resolve=>page.once('close',resolve));
  }finally{await close()}
 })().catch(error=>{console.error(error);process.exitCode=1});
}
