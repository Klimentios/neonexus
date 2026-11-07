# NEONEXUS - one-click install for Windows 10/11.
# Double-click install.bat, or run: powershell -ExecutionPolicy Bypass -File install.ps1
# Installs Python 3.12 if missing (winget), the Python packages in .venv, starts the room
# and the agents whose CLI is installed, and opens the browser. Safe to run again.
# Set NEONEXUS_NO_START=1 to install without starting.
# This file must stay pure ASCII: Windows PowerShell 5.1 reads BOM-less files as ANSI.
$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot
$Root = $PSScriptRoot

function Say($t)  { Write-Host "`n==> $t" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  + $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  ! $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host "`nInstall failed: $t" -ForegroundColor Red; exit 1 }

Say "NEONEXUS installer (Windows)"

# ------------------------------------------------------------ 1. Python 3.11+
$VersionCheck = "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"

# returns the command as an array: exe followed by its arguments
function Find-Python {
    $candidates = @(
        @("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"),
        @("python"), @("python3"),
        @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"),
        @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"),
        @("$env:ProgramFiles\Python313\python.exe"),
        @("$env:ProgramFiles\Python312\python.exe")
    )
    foreach ($c in $candidates) {
        $exe = $c[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $rest = @()
        if ($c.Count -gt 1) { $rest = $c[1..($c.Count - 1)] }
        try {
            & $exe @rest -c $VersionCheck 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return ,$c }
        } catch {}
    }
    return $null
}

function Invoke-Py($cmd, [string[]]$more) {
    $exe = $cmd[0]
    $rest = @()
    if ($cmd.Count -gt 1) { $rest = $cmd[1..($cmd.Count - 1)] }
    & $exe @rest @more
}

$py = Find-Python
if (-not $py) {
    Say "Installing Python 3.12"
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { Warn "winget exited with code $LASTEXITCODE" }
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        $py = Find-Python
    } else {
        Warn "winget is not available on this PC."
    }
    if (-not $py) {
        Write-Host "  Install Python 3.12 from https://www.python.org/downloads/windows/"
        Write-Host "  (tick 'Add python.exe to PATH'), then run install.bat again."
        exit 1
    }
}
$pyVersion = Invoke-Py $py @("--version")
Ok "Python: $pyVersion ($($py -join ' '))"

# ------------------------------------------------------------ 2. Python packages in .venv
Say "Preparing the Python environment"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"

function Test-Venv {
    if (-not (Test-Path -LiteralPath $venvPy)) { return $false }
    & $venvPy -c $VersionCheck 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { return $false }
    & $venvPy -m pip --version 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

if ((Test-Path -LiteralPath ".venv") -and -not (Test-Venv)) {
    Warn "Existing .venv is broken or too old, recreating it"
    Remove-Item -Recurse -Force -LiteralPath ".venv"
}
if (-not (Test-Path -LiteralPath ".venv")) {
    Invoke-Py $py @("-m", "venv", ".venv")
    if ($LASTEXITCODE -ne 0) { Fail "python -m venv failed (exit $LASTEXITCODE)" }
}
if (-not (Test-Venv)) { Fail "the virtual environment in $Root\.venv has no working pip" }

& $venvPy -m pip install -q --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed (exit $LASTEXITCODE)" }
& $venvPy -m pip install -q --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "installing requirements.txt failed (exit $LASTEXITCODE) - check the network" }
Ok "packages installed in $Root\.venv"

# ------------------------------------------------------------ 3. Node.js (optional)
if (Get-Command npm -ErrorAction SilentlyContinue) { Ok "Node.js: $(node --version)" }
else { Warn "Node.js not found. Optional: winget install OpenJS.NodeJS.LTS - needed to add Claude Code / Codex / Gemini CLI from the app." }

# Agent folders (~\NEONEXUS) are created by the app on its first start.

# ------------------------------------------------------------ 4. Start
if ($env:NEONEXUS_NO_START) {
    Say "Installed (start skipped). Start: run install.bat again"
    exit 0
}

# the port as run.py sees it (config.toml + config.local.toml + AGENTCHATTR_PORT)
$port = 8300
$out = & $venvPy -c "import config_loader as c; print('PORT', c.load_config()['server']['port'])" 2>$null
if ($LASTEXITCODE -eq 0) {
    foreach ($line in @($out)) { if ("$line" -match '^PORT (\d+)') { $port = [int]$Matches[1] } }
}
$url = "http://127.0.0.1:$port"

function Test-Web {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "$url/" | Out-Null; return $true } catch { return $false }
}

Say "Starting NEONEXUS"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
$log = Join-Path $Root "data\server.log"
$errLog = Join-Path $Root "data\server-error.log"
if (Test-Web) {
    Ok "already running at $url"
} else {
    $proc = Start-Process -PassThru -WindowStyle Hidden -FilePath $venvPy -ArgumentList "run.py" `
        -WorkingDirectory $Root -RedirectStandardOutput $log -RedirectStandardError $errLog
    Set-Content -LiteralPath (Join-Path $Root "data\server.pid") -Value $proc.Id -Encoding ascii
    $up = $false
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Web) { $up = $true; break }
        if ($proc.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $up) {
        if (Test-Path -LiteralPath $errLog) { Get-Content -LiteralPath $errLog -Tail 20 }
        Fail "the server did not answer at $url. Logs: $log, $errLog"
    }
    Ok "server running (pid $($proc.Id))"
}

foreach ($a in @("claude", "codex", "gemini")) {
    & $venvPy council_ext.py installed $a 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Start-Process -WindowStyle Minimized -FilePath $venvPy -ArgumentList "wrapper.py $a" -WorkingDirectory $Root
        Ok "$a started"
    }
}
Start-Process $url
Say "Done. NEONEXUS is at $url"
Write-Host "  Next: open 'Connect AI' in the app to add your subscriptions, API keys or local models."
Write-Host "  Stop the room: taskkill /PID $(Get-Content -LiteralPath (Join-Path $Root 'data\server.pid') -ErrorAction SilentlyContinue) /F   Start again: install.bat"
