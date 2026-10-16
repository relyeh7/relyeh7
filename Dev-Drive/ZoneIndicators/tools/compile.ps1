# Compiles one .mq5 of ZoneIndicators with metaeditor64 and prints the literal compiler result.
# <ZoneIndicators\X.mqh> includes resolve against the project's MQL5 folder via /inc (nothing copied to a terminal).
# Gate: exit 0 only with "0 errors" AND (unless -AllowWarnings) "0 warnings".
# Usage: powershell -NoProfile -File tools\compile.ps1 -File MQL5\Indicators\SMC_ZonesInd\SMC_ZonesInd.mq5
param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$MetaEditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe",
    [switch]$AllowWarnings
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $MetaEditor)) { Write-Error "metaeditor64.exe not found at $MetaEditor"; exit 2 }
$root = Split-Path -Parent $PSScriptRoot
$inc  = Join-Path $root "MQL5"
$full = (Resolve-Path $File).Path
$log  = "$full.log"
if (Test-Path $log) { Remove-Item $log -Force }
& $MetaEditor /compile:"$full" /inc:"$inc" /log:"$log" | Out-Null
if (-not (Test-Path $log)) { Write-Error "metaeditor produced no log"; exit 3 }
# metaeditor logs are UTF-16
$lines  = Get-Content $log -Encoding Unicode
$issues = $lines | Where-Object { $_ -match " : (error|warning) " }
$result = $lines | Where-Object { $_ -match "Result:" } | Select-Object -Last 1
Write-Output ("== " + (Split-Path $full -Leaf))
$issues | ForEach-Object { Write-Output $_ }
Write-Output $result
if ($result -notmatch "\b0 errors\b") { exit 1 }
if (-not $AllowWarnings -and $result -notmatch "\b0 warnings\b") { exit 1 }
exit 0
