# WOZLY — Seed AI Knowledge Base
# Run this ONCE after setup to load learning resources into the AI.
# Right-click → Run with PowerShell

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   WOZLY — Seeding Knowledge Base" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This downloads learning resources from MDN, scikit-learn," -ForegroundColor Gray
Write-Host "Python docs etc. and stores them for the AI to use." -ForegroundColor Gray
Write-Host "Takes 3-5 minutes. Make sure the backend is running first!" -ForegroundColor Gray
Write-Host ""

$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try { $ver = & $cmd --version 2>&1; if ($ver -match "Python 3\.") { $python = $cmd; break } } catch {}
}

Set-Location "$PSScriptRoot\backend"
& $python app/rag/ingestion.py

Write-Host ""
Write-Host "Knowledge base seeded! The AI can now find real resources." -ForegroundColor Green
Read-Host "Press Enter to close"
