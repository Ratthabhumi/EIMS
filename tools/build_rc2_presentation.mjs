// Uses the bundled artifact runtime; no downloads, services or network.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const runtime=process.env.EIMS_ARTIFACT_RUNTIME,skill=process.env.EIMS_PRESENTATIONS_SKILL;
if(!runtime||!skill)throw Error('Set the existing bundled runtime and presentation skill paths');
process.env.RUNTIME_NODE_MODULES ??= path.join(runtime,'node/node_modules');
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(runtime,'node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs')));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')));
const root=process.cwd(),output=path.join(root,'docs/delivery/rc2-20261101'),qa=path.join(root,'test-results/rc2-artifacts');
await fs.mkdir(output,{recursive:true});await fs.mkdir(qa,{recursive:true});
const original=await fs.readFile('docs/presentation/EIMS_PRESENTATION_SOURCE_2026.md','utf8');
const sections=original.split(/^## Slide \d+: /m).slice(1);
const content=[
['EIMS log investigation',['Evidence grounded multi vendor analysis','Ratthabhumi Peansukmanee','Computer Engineering International Program, KMITL','Cooperative education project, 2026']],
['Cooperative education context',['Enterprise infrastructure produces fragmented operational evidence.','The prototype supports traceable collection and investigation.','Graduation focus: a bounded Analyzer workflow.','Host and supervisor details require author confirmation.']],
['The evidence problem',['Logs arrive from different vendors and disconnected systems.','A repeated error message does not establish its physical cause.','Analysts need the original file, line and surrounding context.','Results must retain uncertainty when evidence is incomplete.']],
['Current graduation objectives',['Classify supported sources and preserve event identity.','Separate observed failure from job outcome and possible causes.','Retain source evidence through user-owned History.','Make evaluation and review reproducible.']],
['System overview',['FastAPI backend and PostgreSQL persistence','Next.js 16.3.0 dashboard with React 19.2.8','Secure BFF and revocable user sessions','Redis and MinIO remain part of the wider architecture.']],
['System boundaries',['Dashboard sends authenticated requests through the BFF.','Analyzer parses records and produces evidence-linked summaries.','PostgreSQL retains owner-scoped investigations.','Offline evaluation injects isolated storage and blocks external network.']],
['Historical offline collection',['September prototype used a portable Windows collector.','Collected evidence was packaged for separate ingestion.','Historical field observations are retained as provenance.','Current physical USB acceptance remains NOT_TESTED.']],
['Historical ingestion',['Evidence fingerprints supported application-level deduplication.','September observations: 49 Windows events and 10 findings.','Historical A9 display evidence is a separate runtime.','Redis and EVTX recovery work remains a separate branch stack.']],
['Current investigation workflow',['Upload synthetic Fortinet, VMware or Windows evidence.','Review source classification, symptoms and uncertainty.','Inspect the saved source excerpt with file and line coordinates.','Reopen History and check ownership in an approved runtime.']],
['Three validation boundaries',['Engineering: synthetic tests and source contracts','Scientific: authentic human judgments on frozen predictions','Runtime: the actual authenticated HTTPS browser workflow','A pass in one boundary does not establish the others.']],
['Measured engineering results',['7335aa2 baseline: 394 automated tests passed.','302 Analyzer, 46 PostgreSQL and 46 USB isolated tests','Eight synthetic counterexamples passed.','12 DEV DRAFT cases and 61 claims have zero human reviews.','Diagnostic accuracy remains NOT_MEASURED.']],
['Five minute offline demonstration',['Fortinet configuration observation: no fabricated failure','VMware CTK: technical failure, physical cause UNKNOWN','Windows 1129: connectivity symptom, missing time preserved','Open source context, then explain next evidence and History limits.']],
['Engineering lessons',['Evidence coordinates must survive serialization and History.','Last observed failure does not establish final job outcome.','RC2 hides empty failure sections and preserves Windows identity.','Review hashes prevent judgments attaching to changed predictions.']],
['Remaining acceptance gates',['Human review of Fortinet, VMware and Windows predictions','Explicitly authorized trusted HTTPS runtime','Author and institutional review of staged report and slides','Owner-approved integration of core PRs with fresh CI']],
['Conclusion and discussion',['The prototype supports traceable, bounded log investigation.','It preserves uncertainty instead of inventing a physical cause.','Current evidence supports engineering claims, not diagnostic accuracy.','Next step: genuine review and authorized runtime acceptance.']]
];
const deck=Presentation.create({slideSize:{width:1280,height:720}});
function text(slide,value,x,y,w,h,size,bold=false,color='#15273a'){
 const sh=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=value;sh.text.style={typeface:'Calibri',fontSize:size,bold,color};return sh;
}
for(let i=0;i<content.length;i++){
 const s=deck.slides.add();s.background.fill='#ffffff';
 text(s,content[i][0],72,55,1136,105,42,true);
 content[i][1].forEach((line,k)=>text(s,line,80,190+k*78,1120,70,29));
 text(s,`EIMS staged academic prototype   •   ${i+1} / 15`,80,660,1120,28,16,false,'#526274');
 s.speakerNotes.text=`Source: docs/presentation/EIMS_PRESENTATION_SOURCE_2026.md, slide ${i+1}.\n${sections[i]}\nRC2 staging note: source UI changes do not alter Analyzer predictions. Baseline 7335aa2 CI 41308596046: 394 PASS. Scientific accuracy NOT_MEASURED. No new browser or USB certification. Original source details are retained here for the presenter; slides condense them.`;
}
const draft=path.join(qa,'candidate.pptx');await (await PresentationFile.exportPptx(deck)).save(draft);
const result=await finalizePresentation({workspaceDir:root,candidatePath:draft,finalPath:path.join(output,'EIMS_RC2_PRESENTATION_STAGED.pptx'),pythonExecutable:path.join(runtime,'python/python.exe'),integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],explicitTotalSlideCount:15,requiredNativeTableOwnerSlides:[],fontPolicy:{basis:'design',families:['Calibri']},verifyArtifactToolImport:true,receiptPath:path.join(qa,'presentation-validation.json')});
console.log(JSON.stringify(result));
for(let i=0;i<deck.slides.items.length;i++){
 const png=await deck.export({slide:deck.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(qa,`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}

