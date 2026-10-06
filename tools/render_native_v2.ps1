param([ValidateSet('development','held-out')][string]$Split = 'development')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$corpusRoot = Join-Path $taskRoot 'validation/native-v2'
if ($Split -eq 'held-out' -and -not (Test-Path -LiteralPath (Join-Path $corpusRoot 'implementation-lock.json'))) { throw 'Held-out implementation must be frozen.' }
$sources = Get-Content -LiteralPath (Join-Path $corpusRoot 'sources.json') -Raw | ConvertFrom-Json
$wordApp = New-Object -ComObject Word.Application
try {
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $wordApp.Options.UpdateLinksAtOpen = $false
    foreach ($source in $sources.papers) {
        if ($source.split -ne $Split -or $null -eq $source.files.'supplement.docx') { continue }
        $inputFile = Join-Path $corpusRoot "papers/$($source.id)/supplement.docx"
        $outDir = Join-Path $taskRoot "build/native-v2/$Split/$($source.id)"
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
        $beforeHash = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash
        $wordDoc = $null
        try {
            $wordDoc = $wordApp.Documents.Open($inputFile, $false, $true, $false)
            $pdfFile = Join-Path $outDir 'word-render.pdf'
            $wordDoc.ExportAsFixedFormat($pdfFile, 17, $false)
            @{case=$source.id; engine='Microsoft Word'; version=$wordApp.Version; pages=$wordDoc.ComputeStatistics(2); source_sha256=$beforeHash.ToLowerInvariant(); role='visual annotation only; original OOXML is the source'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outDir 'render.json') -Encoding utf8
        } finally {
            if ($null -ne $wordDoc) { $wordDoc.Close(0); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDoc) | Out-Null }
        }
        if ((Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash -ne $beforeHash) { throw 'Source bytes changed' }
        Get-Content -LiteralPath (Join-Path $outDir 'render.json')
    }
} finally {
    $wordApp.Quit(0)
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp) | Out-Null
}
