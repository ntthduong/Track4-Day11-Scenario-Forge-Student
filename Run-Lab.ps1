# Support the real alphanumeric student ID through the runner's documented override.
param(
    [ValidateSet('world', 'replay', 'mc', 'hunt', 'estimate', 'fix', 'export', 'mine', 'all')]
    [string]$Step = 'all',
    [string]$Hazard = 'hazard.json',
    [switch]$Quick
)
$ErrorActionPreference = 'Stop'
$reportLine = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'REPORT.md') -TotalCount 1
if ($reportLine -notmatch '^MSSV:\s*([A-Za-z0-9]+)\s*$') {
    throw 'Fill the first line of REPORT.md with MSSV: <student ID>.'
}
$studentId = $Matches[1]
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements.txt first; see SUBMISSION.md.'
}
$previousId = $env:LAB11_MSSV
try {
    $env:LAB11_MSSV = $studentId
    $runnerArgs = @('-u', (Join-Path $PSScriptRoot 'run_all.py'), $Step, $Hazard)
    if ($Quick) { $runnerArgs += '--quick' }
    & $pythonPath @runnerArgs
    $runnerExit = $LASTEXITCODE
} finally {
    if ($null -eq $previousId) {
        Remove-Item Env:LAB11_MSSV -ErrorAction SilentlyContinue
    } else {
        $env:LAB11_MSSV = $previousId
    }
}
exit $runnerExit
