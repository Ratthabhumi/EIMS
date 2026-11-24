$ErrorActionPreference = "Stop"
$src = "C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
$outDir = "C:\Users\MewMew\AppData\Local\Temp\eims_final_review_audit\abstract_render"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$pdf = Join-Path $outDir "abstract_check.pdf"

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $null
try {
  $doc = $word.Documents.Open($src, $false, $true) # ReadOnly open for render
  # Export PDF
  # 17 = wdExportFormatPDF
  $doc.ExportAsFixedFormat($pdf, 17)
  $pages = $doc.ComputeStatistics(2)
  Write-Host "TOTAL_PAGES=$pages"
  Write-Host "PDF=$pdf"

  # Locate abstract pages via Find
  $find = $doc.Content.Find
  $find.ClearFormatting() | Out-Null
  $find.Text = "บทคัดย่อ"
  $find.Forward = $true
  $find.Wrap = 0
  if ($find.Execute()) {
    $thaiPage = $doc.Range(0, $find.Parent.Start).Information(3) # wdActiveEndPageNumber=3? Actually wdActiveEndAdjustedPageNumber=4
    # Information(1)=wdActiveEndPageNumber in some; use 3 = wdActiveEndAdjustedPageNumber in Word VBA: wdActiveEndPageNumber = 3
    Write-Host "THAI_HEADING_PAGE=$($doc.Bookmarks.Item('\Sel').Range.Information(3))"
  }

  # Better: iterate paragraphs
  $thaiStart = $null; $thaiKw = $null; $enStart = $null; $enKw = $null
  foreach ($p in $doc.Paragraphs) {
    $t = $p.Range.Text.Trim()
    if ($t -eq "บทคัดย่อ" -and -not $thaiStart) { $thaiStart = $p.Range.Information(3) }
    if ($t.StartsWith("คำสำคัญ:") -and -not $thaiKw) { $thaiKw = $p.Range.Information(3) }
    if ($t -eq "ABSTRACT" -and -not $enStart) { $enStart = $p.Range.Information(3) }
    if ($t.StartsWith("Keywords:") -and -not $enKw) { $enKw = $p.Range.Information(3) }
    if ($t.StartsWith("Acknowledgments")) { break }
  }
  Write-Host "THAI_HEADING_PAGE=$thaiStart"
  Write-Host "THAI_KEYWORDS_PAGE=$thaiKw"
  Write-Host "EN_HEADING_PAGE=$enStart"
  Write-Host "EN_KEYWORDS_PAGE=$enKw"

  # Font sample from abstract body
  foreach ($p in $doc.Paragraphs) {
    $t = $p.Range.Text.Trim()
    if ($t.StartsWith("ผลการทดสอบอัตโนมัติ") -or $t.StartsWith("The 20 November 2026 backend-final-closure") -or $t.StartsWith("Enterprise infrastructure management across")) {
      $f = $p.Range.Font
      Write-Host ("FONT_SAMPLE name={0} size={1} bold={2} text={3}" -f $f.Name, $f.Size, $f.Bold, $t.Substring(0, [Math]::Min(60, $t.Length)))
    }
    if ($t -eq "บทคัดย่อ" -or $t -eq "ABSTRACT") {
      $f = $p.Range.Font
      Write-Host ("HEADING name={0} size={1} bold={2} text={3}" -f $f.NameFarEast, $f.Size, $f.Bold, $t)
      Write-Host ("HEADING_ASCII_NAME={0}" -f $f.Name)
    }
    if ($t.StartsWith("คำสำคัญ:") -or $t.StartsWith("Keywords:")) {
      $f = $p.Range.Font
      Write-Host ("KW name={0}/{1} size={2} bold={3}" -f $f.Name, $f.NameFarEast, $f.Size, $f.Bold)
    }
  }
}
finally {
  if ($doc) { $doc.Close($false) | Out-Null }
  $word.Quit() | Out-Null
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
  [GC]::Collect()
}
