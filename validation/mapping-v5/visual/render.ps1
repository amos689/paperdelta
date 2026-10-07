$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$inputRoot = Join-Path $taskRoot 'validation/mapping-v5/tasks'
$outputRoot = Join-Path $taskRoot 'build/mapping-v5-render'
if (Test-Path -LiteralPath $outputRoot) { throw 'Preserve previous render outputs.' }
New-Item -ItemType Directory -Path $outputRoot | Out-Null
$wordApp = New-Object -ComObject Word.Application
$records = @()
try {
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $wordApp.Options.UpdateLinksAtOpen = $false
    $cases = @(
        @('development', 'D03', 'docx'), @('development', 'D07', 'docx'),
        @('held-out', 'H03', 'docx'), @('held-out', 'H09', 'docx'),
        @('development', 'D06', 'pdf'), @('development', 'D10', 'pdf'),
        @('held-out', 'H06', 'pdf'), @('held-out', 'H11', 'pdf')
    )
    foreach ($case in $cases) {
        $relative = "$($case[0])/$($case[1])/project/paper/manuscript.$($case[2])"
        $inputFile = (Resolve-Path -LiteralPath (Join-Path $inputRoot $relative)).Path
        $beforeHash = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash
        $rendered = $inputFile
        $record = @{id=$case[1]; original=$relative; source_sha256=$beforeHash.ToLowerInvariant()}
        if ($case[2] -eq 'docx') {
            $rendered = Join-Path $outputRoot "$($case[1]).word.pdf"
            $wordDoc = $null
            try {
                $wordDoc = $wordApp.Documents.Open($inputFile, $false, $true, $false)
                $wordDoc.ExportAsFixedFormat($rendered, 17, $false)
                $record.engine = 'Microsoft Word'
                $record.version = $wordApp.Version
                $record.rendered_pages = $wordDoc.ComputeStatistics(2)
            } finally {
                if ($null -ne $wordDoc) {
                    $wordDoc.Close(0)
                    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDoc) | Out-Null
                }
            }
        } else {
            $record.engine = 'Original PDF / Poppler'
        }
        if ((Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash -ne $beforeHash) {
            throw 'An original document was modified.'
        }
        $imagePrefix = Join-Path $outputRoot $case[1]
        & pdftoppm -f 1 -l 1 -scale-to 1500 -png -singlefile $rendered $imagePrefix
        if ($LASTEXITCODE -ne 0) { throw 'PDF rasterization failed.' }
        $record.png_sha256 = (Get-FileHash -LiteralPath "$imagePrefix.png" -Algorithm SHA256).Hash.ToLowerInvariant()
        $records += $record
    }
    @{purpose='Visual verification of authored original inputs before implementation tuning'; cases=$records} |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot 'evidence.json') -Encoding utf8
    Write-Output "Rendered $($records.Count) original native documents without changing input bytes."
} finally {
    $wordApp.Quit(0)
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp) | Out-Null
}
