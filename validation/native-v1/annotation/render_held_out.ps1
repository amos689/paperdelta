param([Parameter(Mandatory=$true)][string]$Case)
$ErrorActionPreference = 'Stop'
if ($Case -notin @('abstract-quality','pet-repeatability')) { throw 'Only named held-out cases' }
if (-not (Test-Path -LiteralPath 'validation/native-v1/implementation-lock.json')) { throw 'Missing implementation lock' }
$taskRoot = (Resolve-Path -LiteralPath 'validation/native-v1').Path
$inputFile = Join-Path $taskRoot "papers/$Case/supplement.docx"
$outDir = (Resolve-Path -LiteralPath "build/native-v1-heldout-annotation/$Case").Path
$pdfFile = Join-Path $outDir 'word-render.pdf'
if (Test-Path -LiteralPath $pdfFile) { throw 'Refuse to overwrite render' }
$beforeHash = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash
$wordApp = New-Object -ComObject Word.Application
$wordDoc = $null
$oldLinks = $wordApp.Options.UpdateLinksAtOpen
$oldFields = $wordApp.Options.UpdateFieldsAtPrint
try {
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $wordApp.Options.UpdateLinksAtOpen = $false
    $wordApp.Options.UpdateFieldsAtPrint = $false
    $wordDoc = $wordApp.Documents.Open($inputFile, $false, $true, $false)
    $wordDoc.ExportAsFixedFormat($pdfFile, 17, $false)
    @{case=$Case; engine='Microsoft Word'; version=$wordApp.Version; pages=$wordDoc.ComputeStatistics(2); source_sha256=$beforeHash.ToLowerInvariant()} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outDir 'render.json') -Encoding utf8
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDoc) | Out-Null }
    $wordApp.Options.UpdateLinksAtOpen = $oldLinks
    $wordApp.Options.UpdateFieldsAtPrint = $oldFields
    $wordApp.Quit(0)
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp) | Out-Null
}
if ((Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash -ne $beforeHash) { throw 'Source bytes changed' }
& 'pdftoppm' -r 115 -png $pdfFile (Join-Path $outDir 'word-page')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-Content -LiteralPath (Join-Path $outDir 'render.json')
