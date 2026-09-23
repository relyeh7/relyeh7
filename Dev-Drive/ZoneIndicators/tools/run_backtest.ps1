# Runs a Strategy Tester pass headless with a [Tester] .ini and prints the report statistics.
# Default terminal: the development/demo terminal H:\Dev-Drive\MT5_MCP\terminal_demo (data folder D4CE...,
# MetaQuotes-Demo). It is NOT a prop-firm terminal. The .ex5 must already be deployed (tools\deploy.ps1).
# Usage: powershell -NoProfile -File tools\run_backtest.ps1 -Ini mt5_tester\SMC_ZonesInd_TestRunner.ini
param(
    [Parameter(Mandatory = $true)][string]$Ini,
    [string]$Terminal   = "H:\Dev-Drive\MT5_MCP\terminal_demo\terminal64.exe",
    [string]$DataFolder = "D4CEFEDAF043B05DA80223FD698C7DF2",
    [int]$TimeoutSec    = 1800,
    [int]$LogTail       = 60
)
$ErrorActionPreference = "Stop"
$forbidden = @("BBFCFA1FB468228B48295BEE2CC083A8", "C6745B67E1546A2DB84AA403800CD795") # H:\MT5_31169 / H:\MT5_31143 (prop)
if ($forbidden -contains $DataFolder) { Write-Error "refusing to use a prop-firm terminal data folder"; exit 2 }
if (-not (Test-Path $Terminal)) { Write-Error "terminal not found: $Terminal"; exit 2 }
$iniFull = (Resolve-Path $Ini).Path
$running = Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Terminal }
if ($running) { Write-Error "that terminal is already running (pid $($running.Id)); /config cannot start a second instance"; exit 3 }

$iniText = Get-Content $iniFull
$report  = ($iniText | Where-Object { $_ -match "^Report=" }) -replace "^Report=", ""
$expert  = ($iniText | Where-Object { $_ -match "^Expert=" }) -replace "^Expert=", ""
Write-Output "== tester: $expert  ini=$iniFull"
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $Terminal -ArgumentList "/config:`"$iniFull`"" -PassThru
if (-not $p.WaitForExit($TimeoutSec * 1000)) {
    Write-Warning "timeout after $TimeoutSec s - killing terminal"
    Stop-Process -Id $p.Id -Force
    exit 4
}
Write-Output ("terminal exited after {0:n0} s (code {1})" -f $sw.Elapsed.TotalSeconds, $p.ExitCode)

# --- agent log (UTF-16), last lines
$agentLogDir = Join-Path $env:APPDATA "MetaQuotes\Tester\$DataFolder\Agent-127.0.0.1-3000\logs"
$agentLog = Get-ChildItem $agentLogDir -Filter "*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
if ($agentLog) {
    Write-Output "== agent log: $($agentLog.FullName) (last $LogTail lines)"
    Get-Content $agentLog.FullName -Encoding Unicode | Select-Object -Last $LogTail | ForEach-Object {
        # columns: code, level, time, source, message -> keep time + message
        $parts = $_ -split "`t"
        if ($parts.Count -ge 5) { "{0}  {1}" -f $parts[2], ($parts[4..($parts.Count-1)] -join " ") } else { $_ }
    }
}

# --- report statistics (label/value pairs, language independent)
if ($report) {
    $htm = if ($report -match "\.htm(l)?$") { $report } else { "$report.htm" }
    if (Test-Path $htm) {
        Write-Output "== report: $htm"
        $raw = Get-Content $htm -Encoding Unicode -Raw
        $pairs = [regex]::Matches($raw, '<td[^>]*>([^<]{2,80}):</td>\s*<td[^>]*><b>([^<]*)</b>')
        foreach ($m in $pairs) {
            $label = $m.Groups[1].Value.Trim()
            $value = $m.Groups[2].Value.Trim()
            if ($value -ne "") { Write-Output ("  {0,-55} {1}" -f $label, $value) }
        }
    } else {
        Write-Warning "report not found: $htm"
    }
}
exit 0
