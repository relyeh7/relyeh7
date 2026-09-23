# Compiles ZoneIndicators programs (indicators + test runners) with the 0 errors / 0 warnings gate.
# Usage: powershell -NoProfile -File tools\build.ps1
# Usage: powershell -NoProfile -File tools\build.ps1 -Target SMC_ZonesInd
param(
    [string]$Target = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$targets = @(
    "MQL5\Indicators\SMC_ZonesInd\SMC_ZonesInd.mq5",
    "MQL5\Indicators\SMC_ZonesInd\SMC_ZonesInd_TestRunner.mq5",
    "MQL5\Indicators\CRT_ZonesInd\CRT_ZonesInd.mq5",
    "MQL5\Indicators\CRT_ZonesInd\CRT_ZonesInd_TestRunner.mq5",
    "MQL5\Indicators\VWAP_ZonesInd\VWAP_ZonesInd.mq5",
    "MQL5\Indicators\VWAP_ZonesInd\VWAP_ZonesInd_TestRunner.mq5"
)

# Filter by -Target if provided
if ($Target -ne "") {
    $targets = $targets | Where-Object {
        $_ -match "\\$Target\\" -or $_ -match "$Target`_TestRunner\.mq5"
    }
}

$failed = 0
foreach ($t in $targets) {
    & powershell -NoProfile -File (Join-Path $PSScriptRoot "compile.ps1") -File (Join-Path $root $t)
    if ($LASTEXITCODE -ne 0) { $failed++ }
}
if ($failed -ne 0) { Write-Output "BUILD FAILED ($failed target(s))"; exit 1 }
Write-Output "BUILD OK (all targets 0 errors / 0 warnings)"
exit 0
