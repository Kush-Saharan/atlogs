# Reset + seed the Atlas demo. Works from ANY directory.
# Paths resolve relative to this script, so your current folder doesn't matter.
#   Usage:  .\demo\reset.ps1
#           .\demo\reset.ps1 --reset-only
#           .\demo\reset.ps1 --pdf "C:\path\to\pdfs"
$py = Join-Path $PSScriptRoot '..\backend\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
  Write-Host "Could not find the backend venv python at: $py"
  Write-Host "Make sure the backend venv exists (backend\.venv)."
  exit 1
}
& $py (Join-Path $PSScriptRoot 'reset_and_seed.py') @args
