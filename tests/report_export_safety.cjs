/* Node's type stripping runs the actual TS helper; no generated mirror. */
const assert = require('node:assert/strict');
(async () => {
  const {escapeReportData} = await import('../clients/dashboard/src/lib/reportSafety.ts');
  const raw = { overview:'<img src=x onerror="alert(1)">', evidence:['<svg onload=alert(2)>', "a & b"], id:7, missing:null };
  const safe=escapeReportData(raw);
  assert.equal(safe.overview,'&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  assert(!safe.evidence[0].includes('<'));
  assert.equal(safe.evidence[1],'a &amp; b');
  assert.equal(safe.id,7); assert.equal(safe.missing,null);
  assert(raw.overview.startsWith('<img')); // original evidence is unchanged
  console.log('PASS: actual report helper escapes nested untrusted content and preserves original evidence.');
})().catch(e=>{console.error(e);process.exitCode=1});
