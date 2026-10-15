/* Real UI -> actual isolated API -> on-disk SQLite -> History retrieval.
 * Start tools.history_sandbox on 3116 and a dedicated UI preview on 3115.
 * API routing forwards bytes to the sandbox; no synthetic response is invented.
 */
const {chromium}=require(process.env.EIMS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const ui=process.env.EIMS_UI_URL || 'http://127.0.0.1:3115';
const api=process.env.EIMS_SANDBOX_URL || 'http://127.0.0.1:3116';
for(const address of [ui,api]) {
 const parsed=new URL(address);
 assert.equal(parsed.hostname,'127.0.0.1','Only dedicated loopback test endpoints are allowed');
 assert(['3115','3116'].includes(parsed.port));
}
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.EIMS_UI_BROWSER || 'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('requestfailed',r=>console.log('Request failed:',new URL(r.url()).pathname,r.failure()?.errorText));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/api/')) {
    const response=await route.fetch({url:api+url.pathname+url.search});
    return route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':'*','access-control-allow-headers':'*'}});
   }
   if(url.origin===ui)return route.continue();
   return route.abort();
  });
  await page.goto(ui+'/analyzer',{waitUntil:'domcontentloaded',timeout:90000});
  const language=page.locator('select').filter({has:page.locator('option[value="en"]')});
  if(await language.count())await language.first().selectOption('en');
  await page.getByRole('button',{name:'Paste Text',exact:true}).click();
  await page.getByLabel('Log evidence text').fill('Log Name: System\nSource: Microsoft-Windows-Kernel-Power\nDate: 2026-10-15T01:00:00Z\nEvent ID: 41\nSynthetic unclean restart <img id="history-injected" src="https://example.invalid/probe">');
  const submitted=page.waitForResponse(r=>r.request().method()==='POST' && /\/api\/v1\/analyze\/$/.test(new URL(r.url()).pathname),{timeout:60000});submitted.catch(()=>{});
  await page.getByRole('button',{name:/Analyze/}).last().click();
  const response=await submitted;assert.equal(response.status(),200);
  const result=await response.json();assert(Number.isInteger(result.historyId));
  const heading=page.getByRole('heading',{name:'Diagnostic Report',exact:true});await heading.waitFor();
  await heading.locator('..').getByRole('button').last().click();
  const row=page.getByRole('button',{name:`Open analysis ${result.historyId}`,exact:true});
  await row.waitFor();await row.press('Enter');
  await page.getByText('Analysis Record Details — Event 41',{exact:true}).waitFor();
  assert.match(await page.locator('body').innerText(),/Synthetic unclean restart/);
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export MD',exact:true}).click();
  const download=await downloadPromise;
  const output=path.join(__dirname,'../test-results/history-export.md');await download.saveAs(output);
  const markdown=await fs.readFile(output,'utf8');
  assert.match(markdown,/Possible explanations \(not confirmed causes\)/);
  assert.match(markdown,/Reported diagnostic confidence/);
  assert(!markdown.includes('Root Causes / Context'));
  await page.evaluate(()=>{
   window.__exportCheck=null;
   new MutationObserver(records=>{for(const r of records)for(const n of r.addedNodes){
    if(n.nodeType===1 && n.style?.top==='-9999px')window.__exportCheck={injected:!!n.querySelector('#history-injected'),text:n.textContent};
   }}).observe(document.body,{childList:true});
  });
  const pdfDownload=page.waitForEvent('download',{timeout:60000});pdfDownload.catch(()=>{});
  await page.getByRole('button',{name:'Export PDF',exact:true}).click();
  await page.waitForFunction(()=>window.__exportCheck!==null,{},{timeout:30000});
  const check=await page.evaluate(()=>window.__exportCheck);
  assert.equal(check.injected,false,'Untrusted log markup must be escaped in actual History PDF DOM');
  assert.match(check.text,/Not supplied/);
  assert(!check.text.includes('Root Causes / Context'));
  const pdf=await pdfDownload;const pdfPath=path.join(__dirname,'../test-results/history-export.pdf');await pdf.saveAs(pdfPath);
  assert.equal((await fs.readFile(pdfPath)).subarray(0,5).toString(),'%PDF-');
  await page.screenshot({path:path.join(__dirname,'../test-results/history-persistence.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: UI submit, actual isolated SQLite API persistence, exact History ID retrieved by keyboard; History MD/PDF export and HTML escaping. No operational services or human results.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
