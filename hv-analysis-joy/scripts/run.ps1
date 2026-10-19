# Session-only interpreter selection; no installation, login or global configuration.
param(
    [Parameter(Mandatory=$true, Position=0)][string]$Script,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$ScriptArguments
)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = $env:RESEARCH_PYTHON
if (-not $pythonPath) {
    $venvPython = Join-Path $skillRoot '.venv\Scripts\python.exe'
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) { $pythonPath = $venvPython }
    elseif (Test-Path -LiteralPath $bundledPython -PathType Leaf) { $pythonPath = $bundledPython }
    else { $command = Get-Command python -ErrorAction SilentlyContinue; if ($command) { $pythonPath = $command.Source } }
}
if (-not $pythonPath -or -not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw 'Python missing. Set session RESEARCH_PYTHON to an existing Python 3.10+ interpreter.' }
$names = @('PYTHONUTF8','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONDONTWRITEBYTECODE='1'
    & $pythonPath -B -X utf8 $Script @ScriptArguments
    $resultCode = $LASTEXITCODE
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
exit $resultCode
