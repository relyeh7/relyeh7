# Deploys ZoneIndicators (Include + Indicators + Experts, sources and .ex5) to ONE MT5 data folder.
# Default: the development/demo terminal D4CEFEDAF043B05DA80223FD698C7DF2 (H:\Dev-Drive\MT5_MCP\terminal_demo,
# MetaQuotes-Demo). The prop-firm data folders (H:\MT5_31169 / H:\MT5_31143) are refused unconditionally.
# Usage: powershell -NoProfile -File tools\deploy.ps1 [-DataFolder <id>] [-SkipBuild]
param(
    [string]$DataFolder = "D4CEFEDAF043B05DA80223FD698C7DF2",
    [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"
$forbidden = @("BBFCFA1FB468228B48295BEE2CC083A8", "C6745B67E1546A2DB84AA403800CD795")
if ($forbidden -contains $DataFolder) { Write-Error "refusing to deploy to a prop-firm terminal"; exit 2 }
$root = Split-Path -Parent $PSScriptRoot
$dst  = Join-Path $env:APPDATA "MetaQuotes\Terminal\$DataFolder\MQL5"
if (-not (Test-Path $dst)) { Write-Error "terminal data folder not found: $dst"; exit 2 }
if (-not $SkipBuild) {
    & powershell -NoProfile -File (Join-Path $PSScriptRoot "build.ps1")
    if ($LASTEXITCODE -ne 0) { exit 1 }
}
$map = @(
    @{ src = "MQL5\Include\ZoneIndicators";        dst = "Include\ZoneIndicators";        filter = "*.mqh" },
    @{ src = "MQL5\Include\Controls";              dst = "Include\Controls";              filter = "*.mqh" },
    @{ src = "MQL5\Include\SMC_ZonesInd";          dst = "Include\SMC_ZonesInd";          filter = "*.mqh" },
    @{ src = "MQL5\Include\CRT_ZonesInd";          dst = "Include\CRT_ZonesInd";          filter = "*.mqh" },
    @{ src = "MQL5\Include\VWAP_ZonesInd";         dst = "Include\VWAP_ZonesInd";         filter = "*.mqh" },
    @{ src = "MQL5\Indicators\SMC_ZonesInd";       dst = "Indicators\SMC_ZonesInd";       filter = "*.mq5" },
    @{ src = "MQL5\Indicators\SMC_ZonesInd";       dst = "Indicators\SMC_ZonesInd";       filter = "*.ex5" },
    @{ src = "MQL5\Indicators\CRT_ZonesInd";       dst = "Indicators\CRT_ZonesInd";       filter = "*.mq5" },
    @{ src = "MQL5\Indicators\CRT_ZonesInd";       dst = "Indicators\CRT_ZonesInd";       filter = "*.ex5" },
    @{ src = "MQL5\Indicators\VWAP_ZonesInd";      dst = "Indicators\VWAP_ZonesInd";      filter = "*.mq5" },
    @{ src = "MQL5\Indicators\VWAP_ZonesInd";      dst = "Indicators\VWAP_ZonesInd";      filter = "*.ex5" },
    @{ src = "MQL5\Experts\ZoneIndicators_Tests";  dst = "Experts\ZoneIndicators_Tests";  filter = "*.mq5" },
    @{ src = "MQL5\Experts\ZoneIndicators_Tests";  dst = "Experts\ZoneIndicators_Tests";  filter = "*.ex5" }
)
foreach ($m in $map) {
    $s = Join-Path $root $m.src
    $d = Join-Path $dst $m.dst
    New-Item -ItemType Directory -Force $d | Out-Null
    Get-ChildItem $s -Filter $m.filter -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $d $_.Name) -Force
        Write-Output ("  {0} -> {1}" -f $_.Name, $d)
    }
}
Write-Output "OK $dst"
