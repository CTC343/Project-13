$ErrorActionPreference = 'Stop'
$taskDocx = 'F:\project13\项目完整运行流程逐步讲解.docx'
$taskPdf = 'F:\project13\work\documents\flow_explanation_20261117\render\review.pdf'
$taskRenderDir = Split-Path -Parent $taskPdf
New-Item -ItemType Directory -Path $taskRenderDir -Force | Out-Null
$taskWord = $null
$taskDocument = $null
try {
    $taskWord = New-Object -ComObject Word.Application
    $taskWord.Visible = $false
    $taskWord.DisplayAlerts = 0
    $taskDocument = $taskWord.Documents.Open($taskDocx, $false, $true)
    $taskDocument.Repaginate()
    $taskPages = $taskDocument.ComputeStatistics(2)
    $taskDocument.ExportAsFixedFormat($taskPdf, 17)
    Write-Output "Exported Word review PDF with $taskPages pages"
}
finally {
    if ($null -ne $taskDocument) {
        $taskDocument.Close(0)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($taskDocument)
    }
    if ($null -ne $taskWord) {
        $taskWord.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($taskWord)
    }
}
