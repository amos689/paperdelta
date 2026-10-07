param([Parameter(Mandatory=$true)][string]$Directory)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$outRoot = (Resolve-Path -LiteralPath $Directory).Path
if (-not $outRoot.StartsWith((Join-Path $taskRoot 'build') + [IO.Path]::DirectorySeparatorChar)) { throw 'Use a validation directory inside build.' }
$wordApp = New-Object -ComObject Word.Application
try {
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $wordApp.Options.UpdateLinksAtOpen = $false
    $records = @()
    foreach ($language in @('en', 'zh-CN')) {
        $inputFile = Join-Path $outRoot "docx/$language.review.docx"
        $beforeHash = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash
        $pdfFile = Join-Path $outRoot "docx/$language.word-render.pdf"
        if (Test-Path -LiteralPath $pdfFile) { throw 'Preserve earlier renders.' }
        $wordDoc = $null
        try {
            $wordDoc = $wordApp.Documents.Open($inputFile, $false, $true, $false)
            $wordDoc.PrintRevisions = $true
            $wordDoc.ExportAsFixedFormat($pdfFile, 17, $false, 0, 0, 1, 1, 7)
            $notes = @()
            foreach ($comment in $wordDoc.Comments) {
                $notes += @{scope=$comment.Scope.Text; text=$comment.Range.Text; author=$comment.Author}
            }
            if ($notes.Count -ne 1 -or $notes[0].scope -ne '5.4×10-1') { throw 'The Word comment does not select the complete original value.' }
            $records += @{language=$language; engine='Microsoft Word'; version=$wordApp.Version; comments=$notes; source_sha256=$beforeHash.ToLowerInvariant(); rendered_pages=$wordDoc.ComputeStatistics(2)}
        } finally {
            if ($null -ne $wordDoc) { $wordDoc.Close(0); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDoc) | Out-Null }
        }
        if ((Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash -ne $beforeHash) { throw 'Source bytes changed.' }
        & pdftoppm -f 1 -l 1 -scale-to 1800 -png -singlefile $pdfFile (Join-Path $outRoot "docx/$language.word-render")
        if ($LASTEXITCODE -ne 0) { throw 'PDF rasterization failed.' }
    }
    @{role='Authored visual verification of comment copies; not product runtime'; cases=$records} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outRoot 'word-render.json') -Encoding utf8
} finally {
    $wordApp.Quit(0)
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp) | Out-Null
}
