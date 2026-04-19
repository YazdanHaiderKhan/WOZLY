# WOZLY — One-Time Setup Script (NO DOCKER NEEDED)
# Run this ONCE before starting the app for the first time.
# Right-click this file → "Run with PowerShell"

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   WOZLY — First Time Setup" -ForegroundColor Cyan
Write-Host "   No Docker needed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Check Python ──────────────────────────────────────────────────────────────
Write-Host "[ 1/5 ] Checking Python..." -ForegroundColor Yellow
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(1[0-9]|[89])") {
            $python = $cmd
            Write-Host "        Found: $ver" -ForegroundColor Green
            break
        }
    } catch {}
}
if (-not $python) {
    Write-Host "  ERROR: Python 3.8+ not found!" -ForegroundColor Red
    Write-Host "  Download from: https://python.org/downloads" -ForegroundColor Red
    Write-Host "  Make sure to check 'Add Python to PATH' during install." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Check Node.js ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 2/5 ] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVer = node --version 2>&1
    Write-Host "        Found: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Node.js not found!" -ForegroundColor Red
    Write-Host "  Download from: https://nodejs.org  (LTS version)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Backend dependencies ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 3/5 ] Installing Python packages (takes 3-5 minutes)..." -ForegroundColor Yellow
Write-Host "        (FastAPI, LangChain, ChromaDB, SQLite driver...)" -ForegroundColor Gray
Set-Location "$root\backend"
& $python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: pip install failed." -ForegroundColor Red
    Write-Host "  Check your internet connection and try again." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "        Python packages installed!" -ForegroundColor Green

# ── Frontend dependencies ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 4/5 ] Installing frontend packages (takes 1-2 minutes)..." -ForegroundColor Yellow
Set-Location "$root\frontend"
npm install --silent
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: npm install failed." -ForegroundColor Red
    Write-Host "  Make sure Node.js is installed from https://nodejs.org" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "        Frontend packages installed!" -ForegroundColor Green

# ── Check .env ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 5/5 ] Checking configuration..." -ForegroundColor Yellow
Set-Location $root
if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "        Created .env — IMPORTANT: Set your GITHUB_TOKEN in .env!" -ForegroundColor Yellow
} else {
    Write-Host "        .env already exists" -ForegroundColor Green
}

# Confirm SQLite mode
Write-Host ""
Write-Host "  Database:  SQLite (file-based, no server needed)" -ForegroundColor Cyan
Write-Host "  Vector DB: ChromaDB local folder (no server needed)" -ForegroundColor Cyan
Write-Host "  LLM:       GitHub Models (free with your GitHub PAT)" -ForegroundColor Cyan

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run START.ps1 to launch the app" -ForegroundColor White
Write-Host "  2. Run SEED_KNOWLEDGE.ps1 to load learning content (run ONCE)" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to close"
