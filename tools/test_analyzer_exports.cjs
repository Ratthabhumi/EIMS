const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const req=require('module').createRequire(path.resolve('clients/dashboard/package.json'));
const ts=req('typescript');
let src;
function run(code,args){const js=ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;return new Function(...Object.keys(args),js)(...Object.values(args));}
const m={exports:{}};run(fs.readFileSync('clients/dashboard/src/lib/report-data.ts','utf8'),{exports:m.exports});
function exported(result,format){
 if(format==='md')return run(src.slice(src.indexOf('    let content ='),src.indexOf('    const blob ='))+'\nreturn content;', {result,item:result,isInc:false,friendly:{title:'Synthetic test'}});
 const container={innerHTML:''};run(src.slice(src.indexOf('      const steps = safe'),src.indexOf('      document.body.appendChild(container)')),{safeResult:m.exports.escapeReportData(result),safeItem:m.exports.escapeReportData(result),container,isInc:false,friendly:{title:'Synthetic test'}});return container.innerHTML;
}
const rows=fs.readFileSync('evaluation/analyzer/results/20261101-priority-full_investigation/predictions.jsonl','utf8').trim().split('\n').map(JSON.parse);
let passed=0;const failures=[];function check(name,f){try{f();passed++;}catch(e){failures.push({name,error:e.message});}}
for(const view of ['app/analyzer/page.tsx','components/AnalyzerHistoryList.tsx']){
src=process.argv.includes('--baseline') ? require('child_process').execFileSync('git',['show','2eef18c:clients/dashboard/src/'+view],{encoding:'utf8'}) : fs.readFileSync('clients/dashboard/src/'+view,'utf8');
for(const format of ['md','pdf']){
 for(const cid of ['fort_config','esxi_tracker','win_policy'])check(view+' '+format+' '+cid,()=>{
 const result=rows.find(r=>r.case_id===cid).native_response,out=exported(result,format);
 assert(!out.includes('Root Causes')&&!out.includes('Resolution Steps'),'export must not upgrade hypotheses/recommendations');
 assert(out.includes(result.eventId),'event identity must survive diagnostic category');
 for(const evidence of result.solutionSummary.evidence||[])assert(out.includes(format==='pdf'?m.exports.escapeReportData(evidence):evidence));
 assert(out.includes('What Is Still Unknown'));
 if(result.eventMetadata?.diagnosticCode)assert(out.includes(result.eventMetadata.diagnosticCode));
 for(const e of result.solutionSummary.evidenceItems||[])assert(out.includes(`${e.sourceFile}:${e.lineNumber}`),'export must retain source coordinates');
 });
 check(view+' '+format+' absent metadata',()=>{const out=exported({eventMetadata:{},solutionSummary:{causes:['Check connectivity'],steps:['Collect more evidence']}},format);assert(!/Localhost|Application|>Error<|undefined/.test(out));assert(out.includes('Not provided'));});
}
}
console.log(JSON.stringify({passed,failures,boundary:'actual export content builders; PDF rasterization/browser download not executed'}));if(failures.length)process.exitCode=1;
