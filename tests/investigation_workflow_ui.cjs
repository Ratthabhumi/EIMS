/* Production UI + intercepted synthetic API only; not a human usability result. */
const {chromium}=require(process.env.EIMS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const base=process.env.EIMS_UI_URL || 'http://127.0.0.1:3115';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.EIMS_UI_BROWSER || 'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const result={eventId:'VEEAM-SESSION-FAILED',provider:'Veeam',historyId:1,bundleId:1,
   files:[{filename:'01_report.txt'},{filename:'02_Task_long.log'}],correlationConfidence:'none',correlationReasons:['No shared identifier'],
   eventMetadata:{sourceFamily:'veeam_vbr',diagnosticCode:'VEEAM-SESSION-FAILED',product:'Veeam'},
   solutionSummary:{overview:'Synthetic observed session failure',causes:['Example hypothesis requiring corroboration'],steps:['Preserve source evidence'],evidence:['Observed failure in synthetic input'],confidence:'low',limitations:['Cause is not established'],evidenceItems:[{sourceFile:'02_Task_long.log',lineNumber:1001,message:'Synthetic task failed'}]},searchResults:[]};
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin===base && !url.pathname.startsWith('/api/'))return route.continue();
   let body={};
   if(url.pathname.endsWith('/analyze/bundle'))body=result;
   else if(url.pathname.includes('/history'))body=url.pathname.endsWith('/stats')?{totalLogs:0,criticalErrors:0,dailyTrends:[],categoryStats:[],providerStats:[]}:[];
   await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},body:JSON.stringify(body)});
  });
  await page.goto(base+'/analyzer',{waitUntil:'domcontentloaded',timeout:90000});
  await page.getByRole('heading',{name:'Log Investigation & Evidence Review',exact:true}).waitFor();
  const language=page.locator('select').filter({has:page.locator('option[value="en"]')});
  if(await language.count())await language.first().selectOption('en');
  await page.getByRole('button',{name:'Evidence Bundle',exact:true}).click();
  const chooser=page.getByRole('button',{name:'Choose evidence bundle files',exact:true});
  const fileChooser=page.waitForEvent('filechooser');await chooser.press('Enter');
  await(await fileChooser).setFiles([
   path.join(__dirname,'../EIMS_supervision_synthetic_demo_files_2026-10-09/01_report.txt'),
   path.join(__dirname,'../EIMS_supervision_synthetic_demo_files_2026-10-09/02_Task_long.log')]);
  await page.getByText('02_Task_long.log',{exact:true}).waitFor();
  await page.getByRole('button',{name:/Analyze/}).last().click();
  await page.getByText('Synthetic observed session failure',{exact:true}).waitFor();
  await page.getByText('Possible explanations (not confirmed causes):',{exact:true}).waitFor();
  await page.getByText('Reported diagnostic confidence:',{exact:false}).waitFor();
  await page.getByText('Cross-file Association',{exact:false}).waitFor();
  await page.getByText('Shared identifiers or timing show an association, not causation.',{exact:true}).waitFor();
  assert.match(await page.locator('body').innerText(),/1001/);
  assert.equal(await page.getByText('Root Causes:',{exact:true}).count(),0);
  const metadataPanel=page.getByText('Event Details',{exact:true}).locator('..');
  assert.equal(await metadataPanel.getByText('Localhost',{exact:true}).count(),0,'missing computer must not be invented');
  assert.equal(await metadataPanel.getByText('Application',{exact:true}).count(),0,'missing log channel must not be invented');
  assert.equal(await metadataPanel.getByText('Not supplied',{exact:true}).count(),3);
  assert.equal(await page.getByText('Number of events: 1',{exact:false}).count(),0,'event count must not be hardcoded');
  await page.screenshot({path:path.join(__dirname,'../test-results/investigation-result.png'),fullPage:true});
  await page.setViewportSize({width:1024,height:768});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  assert.deepEqual(errors,[]);
  console.log('PASS: real production UI; keyboard bundle selection, 2-file feedback, evidence line, uncertainty/confidence labels, 1024px layout. API is intercepted synthetic data; no human evaluation.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
