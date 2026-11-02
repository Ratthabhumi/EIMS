// Render actual shared live/History React components. No listener or browser.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const req=require('module').createRequire(path.resolve('clients/dashboard/package.json'));
const ts=req('typescript'),React=req('react'),{renderToStaticMarkup}=req('react-dom/server');
function load(file){
 const m={exports:{}};
 const source=process.argv.includes('--baseline') && file==='components/AnalysisResultDetail.tsx' ? require('child_process').execFileSync('git',['show','7335aa2:clients/dashboard/src/'+file],{encoding:'utf8'}) : fs.readFileSync(path.resolve('clients/dashboard/src',file),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 new Function('require','module','exports',code)(id=>id==='./EvidenceSourceReview'?load('components/EvidenceSourceReview.tsx'):id==='../lib/api'?{apiUrl:x=>x}:req(id),m,m.exports);
 return m.exports;
}
const Component=load('components/AnalysisResultDetail.tsx').default;
const rows=fs.readFileSync('evaluation/analyzer/results/20261101-priority-full_investigation/predictions.jsonl','utf8').trim().split('\n').map(JSON.parse);
const render=(cid,language)=>renderToStaticMarkup(React.createElement(Component,{result:rows.find(r=>r.case_id===cid).native_response,language}));
let passed=0; const failures=[]; function check(name,fn){try{fn();passed++;}catch(e){failures.push({name,error:e.message});}}
for(const language of ['en','th']){
 check(language+' informational rendering',()=>{const fort=render('fort_config',language);
 assert(!fort.includes(language==='en'?'Failure Sequence (Observed)':'ลำดับความล้มเหลว (ที่พบจริง)'),'informational config must not render None as a failure');
 assert(fort.includes('0100044547') && fort.includes('Configuration setting error-log-retention'));
 }); check(language+' observed chronology',()=>{const vm=render('esxi_tracker',language);
 assert(vm.includes(language==='en'?'Last observed failure:':'ความล้มเหลวล่าสุดที่พบ:'));
 assert(!vm.includes('Terminal failure:'));
 }); check(language+' Windows identity',()=>{const win=render('win_policy',language);
 assert(win.includes('Event ID: 1129'),'diagnostic category must not hide event identity');
 assert(win.includes(language==='en'?'Investigation summary':'สรุปการวิเคราะห์'));
 assert.equal(rows.find(r=>r.case_id==='win_policy').native_response.eventMetadata.timestamp,'');
 });
}
console.log(JSON.stringify({passed,failures,boundary:'actual React server rendering only; not HTTPS browser acceptance'}));

if(failures.length)process.exitCode=1;
