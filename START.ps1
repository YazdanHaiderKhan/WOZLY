# WOZLY - Start the App (NO DOCKER)
# Run this every time you want to use WOZLY.
# Right-click -> "Run with PowerShell"

$root = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   WOZLY - Starting..." -ForegroundColor Cyan
Write-Host "   --- No Docker needed ---" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Detect Python
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.") { $python = $cmd; break }
    } catch {}
}
if (-not $python) {
    Write-Host "ERROR: Python not found! Run SETUP.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Check packages installed
$checkPkg = & $python -c "import fastapi" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python packages not installed. Run SETUP.ps1 first!" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Start Backend
Write-Host "Starting Backend (FastAPI + SQLite)..." -ForegroundColor Yellow
$backendArgs = "-NoExit -Command `"Set-Location '$root\backend'; & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`""
$backendProc = Start-Process -FilePath "powershell" -ArgumentList $backendArgs -PassThru -WindowStyle Normal
Write-Host "  Backend window opened - wait for it to show 'Application startup complete'" -ForegroundColor Gray

# Wait for backend to be ready
Write-Host "  Waiting for backend..." -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Write-Host "  ." -NoNewline -ForegroundColor Gray
}
Write-Host ""

if ($ready) {
    Write-Host "  Backend is ready!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  WARNING: Backend hasn't responded yet." -ForegroundColor Yellow
    Write-Host "  Check the backend PowerShell window for any error messages." -ForegroundColor Yellow
    Write-Host "  Common fixes:" -ForegroundColor Yellow
    Write-Host "    - Make sure GITHUB_TOKEN is set in .env" -ForegroundColor White
    Write-Host "    - Run SETUP.ps1 if packages aren't installed" -ForegroundColor White
    Write-Host ""
}

# Start Frontend
Write-Host "Starting Frontend - React..." -ForegroundColor Yellow
$frontendArgs = "-NoExit -Command `"Set-Location '$root\frontend'; npm run dev`""
$frontendProc = Start-Process -FilePath "powershell" -ArgumentList $frontendArgs -PassThru -WindowStyle Normal
Write-Host "  Frontend window opened - wait for it to show 'Local: http://localhost:3000'" -ForegroundColor Gray

# Open browser
Write-Host ""
Write-Host "  Opening browser in 6 seconds..." -ForegroundColor Gray
Start-Sleep -Seconds 6
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   WOZLY is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  App:       http://localhost:3000" -ForegroundColor Cyan
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  DB file:   backend\wozly.db  (SQLite, auto-created)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To stop: close the two PowerShell windows." -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to close this window (app keeps running)"
