# Export only newly staged artifacts using installed Office. Do not touch user sessions.
$ErrorActionPreference='Stop'
if (Get-Process WINWORD,POWERPNT -ErrorAction SilentlyContinue) { throw 'Close Office yourself before this isolated staged export; no existing process will be stopped.' }
$root=Split-Path $PSScriptRoot -Parent
$docPath=Join-Path $root 'docs/delivery/rc2-20261101/EIMS_RC2_REPORT_REVIEW.docx'
$deckPath=Join-Path $root 'docs/delivery/rc2-20261101/EIMS_RC2_PRESENTATION_STAGED.pptx'
foreach($p in @($docPath,$deckPath)) { if(-not (Test-Path -LiteralPath $p)){throw "Missing staged input: $p"}; if(Test-Path -LiteralPath ([IO.Path]::ChangeExtension($p,'pdf'))){throw 'PDF already exists; preserve prior exports and use a new staging revision.'} }
$word=$null;$doc=$null
try { $word=New-Object -ComObject Word.Application;$word.Visible=$false;$word.DisplayAlerts=0;$word.AutomationSecurity=3;$doc=$word.Documents.Open($docPath,$false,$false);$doc.Fields.Update()|Out-Null;$doc.Repaginate();$doc.Save();$doc.ExportAsFixedFormat(([IO.Path]::ChangeExtension($docPath,'pdf')),17) }
finally {if($null -ne $doc){$doc.Close(0)};if($null -ne $word){$word.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)}}
$ppt=$null;$deck=$null
try {$ppt=New-Object -ComObject PowerPoint.Application;$ppt.AutomationSecurity=3;$deck=$ppt.Presentations.Open($deckPath,-1,0,0);$deck.SaveAs(([IO.Path]::ChangeExtension($deckPath,'pdf')),32)}
finally {if($null -ne $deck){$deck.Close()};if($null -ne $ppt){$ppt.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)}}
