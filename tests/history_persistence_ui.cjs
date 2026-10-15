/* Real UI -> actual isolated API -> on-disk SQLite -> History retrieval.
 * Start tools.history_sandbox on 3116 and a dedicated UI preview on 3115.
 * API routing forwards bytes to the sandbox; no synthetic response is invented.
 */
const {openEvaluation}=require('../tools/open_history_evaluation.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const receipt=path.join(__dirname,'../test-results/facilitator-preflight.json');
const deadline=setTimeout(()=>{console.error('FAIL: facilitator preflight exceeded 120 seconds');process.exit(1)},120000);
(async()=>{
 await fs.writeFile(receipt,JSON.stringify({tasks:'RUNNING',exports:'NOT RUN',humanEvaluation:false}));
 // Exercise the facilitator's exact identity check and forwarding path.
 const {browser,page,close}=await openEvaluation({headless:process.env.EIMS_PREFLIGHT_HEADED!=='1'});
 try{
  await page.setViewportSize({width:1366,height:900});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('requestfailed',r=>console.log('Request failed:',new URL(r.url()).pathname,r.failure()?.errorText));
  // Wait for an observable React state transition before setting language.
  // A select in server-rendered HTML can change before hydration attaches it.
  await page.getByRole('button',{name:'Evidence Bundle',exact:true}).click();
  await page.getByRole('button',{name:'Choose evidence bundle files',exact:true}).waitFor();
  await page.getByRole('button',{name:'Paste Text',exact:true}).click();
  const language=page.locator('select').filter({has:page.locator('option[value="en"]')});
  await language.first().selectOption('en');
  const windows=await fs.readFile(path.join(__dirname,'fixtures/windows_shutdown_synthetic.txt'),'utf8');
  await page.getByLabel('Log evidence text').fill(windows.trimEnd()+'\nSynthetic unclean restart <img id="history-injected" src="https://example.invalid/probe">');
  const submitted=page.waitForResponse(r=>r.request().method()==='POST' && /\/api\/v1\/analyze\/$/.test(new URL(r.url()).pathname),{timeout:60000});submitted.catch(()=>{});
  await page.getByRole('button',{name:/Analyze/}).last().click();
  const response=await submitted;assert.equal(response.status(),200);
  const result=await response.json();assert(Number.isInteger(result.historyId));
  assert.deepEqual(result.solutionSummary.causes,[]);
  assert.match(result.solutionSummary.evidence.join(' '),/6008/);
  assert.match(result.solutionSummary.limitations.join(' '),/does not prove/);
  const heading=page.getByRole('heading',{name:'Diagnostic Report',exact:true});await heading.waitFor();
  if(!process.argv.includes('--tasks-only')) {
   const pending=page.waitForEvent('download');
   await page.getByRole('button',{name:'Export MD',exact:true}).click();
   const output=path.join(__dirname,'../test-results/analysis-export.md');
   await(await pending).saveAs(output);
   assert.match(await fs.readFile(output,'utf8'),/6008/);
  }
  await heading.locator('..').getByRole('button').last().click();
  const row=page.getByRole('button',{name:`Open analysis ${result.historyId}`,exact:true});
  await row.waitFor();await row.press('Enter');
  await page.getByText('Analysis Record Details — Event 41',{exact:true}).waitFor();
  assert.match(await page.locator('body').innerText(),/Synthetic unclean restart/);
  await page.getByRole('button',{name:'Close details',exact:true}).click();
  // T2/T3: actual negative bundle, original fixture bytes and line provenance.
  await page.getByRole('button',{name:'Evidence Bundle',exact:true}).click();
  const chosen=page.waitForEvent('filechooser');chosen.catch(()=>{});
  await page.getByRole('button',{name:'Choose evidence bundle files',exact:true}).press('Enter');
  await(await chosen).setFiles(['01_report.txt','02_Task_long.log'].map(name=>path.join(__dirname,'../EIMS_supervision_synthetic_demo_files_2026-10-09',name)));
  const bundled=page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname==='/api/v1/analyze/bundle',{timeout:60000});bundled.catch(()=>{});
  await page.getByRole('button',{name:/Analyze/}).last().click();
  const bundleResponse=await bundled;assert.equal(bundleResponse.status(),200,await bundleResponse.text());
  const bundle=await bundleResponse.json();assert.equal(bundle.correlationConfidence,'none');
  assert(bundle.solutionSummary.evidenceItems.some(i=>i.sourceFile==='02_Task_long.log' && i.lineNumber===1001));
  await heading.waitFor();
  assert.match(await page.locator('body').innerText(),/1001/);
  assert.match(await page.locator('body').innerText(),/02_Task_long\.log/);
  await heading.locator('..').getByRole('button').last().click();
  await page.getByRole('button',{name:`Open analysis ${bundle.historyId}`,exact:true}).press('Enter');
  await page.getByRole('button',{name:'Close details',exact:true}).waitFor();
  assert.match(await page.locator('body').innerText(),/1001/);
  await page.screenshot({path:path.join(__dirname,'../test-results/history-persistence.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  await fs.writeFile(receipt,JSON.stringify({tasks:'PASS',exports:'NOT RUN',headed:process.env.EIMS_PREFLIGHT_HEADED==='1',humanEvaluation:false}));
  console.log('PASS: facilitator T1-T4 tasks; real SQLite API, shutdown uncertainty, negative Veeam relationship, original file/line1001, exact saved History IDs via keyboard. Automated preflight only.');
  if(process.argv.includes('--tasks-only'))return;
  await page.getByRole('button',{name:'Close details',exact:true}).click();
  await page.getByRole('button',{name:`Open analysis ${result.historyId}`,exact:true}).press('Enter');
  await page.getByText('Analysis Record Details — Event 41',{exact:true}).waitFor();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export MD',exact:true}).click();
  const download=await downloadPromise;
  const output=path.join(__dirname,'../test-results/history-export.md');
  try {await download.saveAs(output)}catch(error){console.log('Download failure state:',{pageClosed:page.isClosed(),browserConnected:browser.isConnected(),failure:await download.failure().catch(()=>null)});throw error}
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
  await fs.writeFile(receipt,JSON.stringify({tasks:'PASS',exports:'PASS',headed:process.env.EIMS_PREFLIGHT_HEADED==='1',humanEvaluation:false}));
  console.log('PASS: facilitator launcher preflight T1-T4; actual isolated SQLite API, 41/6008 uncertainty, negative Veeam association, original line1001, exact History IDs via keyboard, MD/PDF escaping. Automated checks only; no human results.');
 }finally{await close()}
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>clearTimeout(deadline));
