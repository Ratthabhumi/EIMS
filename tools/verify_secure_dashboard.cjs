// Prepared acceptance test; no injected JWT or Authorization header.
// Requires the actual Dashboard+BFF and isolated login/DB harness to be running.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.EIMS_PLAYWRIGHT_MODULE||'playwright');
const base=process.env.EIMS_TEST_BROWSER_BASE_URL||'https://localhost:3449';
const password='synthetic-test-password-only';
(async()=>{
 let browser;const report={status:'FAIL',boundary:'Actual browser login, no injected bearer',checks:[]};
 try{
  browser=await chromium.launch({channel:'msedge',headless:true});
  const options={viewport:{width:1400,height:1000},ignoreHTTPSErrors:process.env.EIMS_TEST_IGNORE_TLS_ERRORS==='1'};
  const owner=await browser.newContext(options),other=await browser.newContext(options);
  let bearerRequests=0;owner.on('request',r=>{if(r.headers().authorization)bearerRequests++});
  async function signIn(context,username){
   const page=await context.newPage();await page.goto(base+'/analyzer');
   await page.getByLabel('Username / ชื่อผู้ใช้').fill(username);await page.getByLabel('Password / รหัสผ่าน').fill(password);
   const response=page.waitForResponse(r=>r.url().endsWith('/api/session/login')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Sign in / เข้าสู่ระบบ',exact:true}).click();
   const r=await response;assert.equal(r.status(),200);assert.deepEqual(await r.json(),{authenticated:true});
   return page;
  }
  const page=await signIn(owner,'synthetic-browser-review');
  await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
  const cookies=await owner.cookies();const cookie=cookies.find(c=>c.name==='eims_session');
  assert(cookie&&cookie.httpOnly&&cookie.secure&&cookie.sameSite==='Strict');
  assert(!(await page.evaluate(()=>document.cookie)).includes('eims_session'));
  assert(!(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}))).includes(cookie.value));
  report.checks.push('Real login; HttpOnly Secure SameSite cookie; no JWT in DOM/storage');
  await page.getByRole('button',{name:'Evidence Bundle',exact:true}).click();
  for(const select of await page.locator('select').all())if(await select.locator('option[value="en"]').count())await select.selectOption('en');
  const root=path.resolve('evaluation/analyzer/results/20261025-controlled-demo-after');
  await page.locator('input[type=file][multiple]').setInputFiles([path.join(root,'a-veeam.txt'),path.join(root,'b-vmware.txt')]);
  const upload=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze/bundle')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();const r=await upload;assert.equal(r.status(),200);const saved=await r.json();
  const summary=page.locator('details summary').first();await summary.waitFor();await summary.focus();await page.keyboard.press('Enter');
  assert(await page.locator('mark').first().isVisible());
  fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:'test-results/secure-source-light.png'});
  await page.getByRole('button',{name:'Back to finding',exact:true}).first().click();assert(await summary.evaluate(e=>document.activeElement===e));
  await page.reload();await page.getByText('Analyzed Log',{exact:true}).first().click();await page.locator('details summary').first().click();
  assert(await page.locator('mark').first().isVisible());await page.evaluate(()=>document.documentElement.classList.add('dark'));await page.screenshot({path:'test-results/secure-history-dark.png'});
  const rows=await (await owner.request.get(base+'/api/eims/api/v1/history')).json();const row=rows.find(x=>x.id===saved.historyId);
  assert.equal(row.username,'synthetic-browser-review');assert.deepEqual(row.solutionSummary,saved.solutionSummary);report.checks.push('Upload, evidence, light/dark, reload and owned PostgreSQL History');
  const otherPage=await signIn(other,'synthetic-browser-other');await otherPage.getByText('Signed in: synthetic-browser-other',{exact:true}).waitFor();
  const otherRows=await (await other.request.get(base+'/api/eims/api/v1/history')).json();assert(!otherRows.some(x=>x.id===saved.historyId));
  const forbidden=await otherPage.evaluate(async id=>(await fetch('/api/eims/api/v1/analyze/followup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({historyId:id,question:'What is observed?',language:'en'})})).status,saved.historyId);assert.equal(forbidden,404);report.checks.push('Second actual-login user cannot list or follow up owner History');
  await page.reload();await page.getByRole('button',{name:'Sign out / ออกจากระบบ',exact:true}).click();
  await page.getByLabel('Username / ชื่อผู้ใช้').waitFor();assert.equal((await owner.request.get(base+'/api/eims/api/v1/history')).status(),401);report.checks.push('Logout clears session and protected access fails');
  const expiry=await browser.newContext(options);const short=await signIn(expiry,'synthetic-expiry');await new Promise(r=>setTimeout(r,3500));await short.reload();
  await short.getByLabel('Username / ชื่อผู้ใช้').waitFor();assert.equal((await expiry.request.get(base+'/api/eims/api/v1/history')).status(),401);
  await short.close();const again=await signIn(expiry,'synthetic-expiry');await again.close();report.checks.push('Real login-issued expiry and reauthentication');
  assert.equal(bearerRequests,0);report.checks.push('Zero manually injected browser Authorization headers');report.status='PASS';
 }catch(error){report.error=String(error);process.exitCode=1}finally{
  if(browser)await browser.close();fs.mkdirSync('test-results',{recursive:true});fs.writeFileSync('test-results/secure-browser-acceptance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }
})();
