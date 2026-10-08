# ============================================================
# GlobalIntelligence — ساخت آرشیو تمیز قابل‌اشتراک
# - .env محلی کاربر هرگز حذف/بازنویسی نمی‌شود؛ فقط از بسته کنار گذاشته می‌شود.
# - کنارگذاشته‌ها: .env، .git، venvها، node_modules، dist، کش‌ها، logها، داده محلی
# - فقط .env.example در بسته می‌ماند.
# اجرا از ریشه مخزن:  powershell -ExecutionPolicy Bypass -File scripts/build_clean_archive.ps1
# ============================================================
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutDir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = "Stop"

$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$zipName = "GlobalIntelligence-clean-$stamp.zip"
$zipPath = Join-Path $OutDir $zipName

$excludeDirs = @(
    ".git", ".venv", "venv", "env",
    "node_modules", "dist", ".vite",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "htmlcov", ".eggs",
    "logs", "data\raw", "data\cache",
    "docker\volumes"
)
$excludeFiles = @(
    ".env",
    "*.log", "*.sqlite", "*.db", "*.pem", "*.key",
    "coverage.xml", ".coverage"
)

Write-Host "repo: $RepoRoot"
Write-Host "out : $zipPath"

Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, "Create")

function Should-Exclude([string]$relPath, [bool]$isDir) {
    $p = $relPath -replace "/", "\"
    foreach ($d in $excludeDirs) {
        if ($p -eq $d -or $p.StartsWith($d + "\") -or $p.Contains("\" + $d + "\")) {
            return $true
        }
    }
    if (-not $isDir) {
        $leaf = Split-Path $p -Leaf
        if ($leaf -eq ".env") { return $true }
        foreach ($pat in $excludeFiles) {
            if ($pat -eq ".env") { continue }
            if ($leaf -like $pat) { return $true }
        }
    }
    return $false
}

$files = Get-ChildItem -Path $RepoRoot -Recurse -Force -File | Where-Object {
    $rel = $_.FullName.Substring($RepoRoot.Length).TrimStart("\", "/")
    -not (Should-Exclude $rel $false)
}

# --- اسکن secret (بدون چاپ مقدار): کلید/رمز غیرخالی و غیر-placeholder ---
$placeholders = @("", "change-me-in-production", "changeme", "example", "xxx", "test")
$violations = @()
foreach ($f in $files) {
    $ext = $f.Extension.ToLower()
    if ($ext -notin @(".env", ".example", ".yml", ".yaml", ".toml", ".json", ".py", ".ts", ".md", ".txt")) { continue }
    if ($f.Name -eq ".env.example") { continue }  # placeholder مجاز
    try { $text = [System.IO.File]::ReadAllText($f.FullName) } catch { continue }
    foreach ($line in $text -split "`n") {
        # فقط سبک env-file: نام UPPERCASE در ابتدای خط (نه متغیرهای کد مثل key=/tokens=)
        if ($line -cmatch "^\s*([A-Z][A-Z0-9_]*(?:KEY|PASSWORD|SECRET|TOKEN)[A-Z0-9_]*)\s*=\s*(.+?)\s*$") {
            $raw = $matches[2].Trim()
            # حذف کامنت انتهای خط (سبک env/py)
            $raw = ($raw -split "#", 2)[0].Trim()
            $val = $raw.Trim('"').Trim("'")
            # مقادیر عددی/boolean ثابت کد هستند، نه secret
            if ($val -match "^[\d.]+$" -or $val -match "^(?i:true|false|none|null)$") { continue }
            if ($val -notin $placeholders -and $val -ne "") {
                $violations += "$($f.FullName.Substring($RepoRoot.Length)): $($matches[1])=<redacted>"
            }
        }
    }
}
if ($violations.Count -gt 0) {
    Write-Host "SECRET SCAN FAILED — موارد مشکوک (مقادیر نمایش داده نمی‌شود):"
    $violations | ForEach-Object { Write-Host "  $_" }
    $zip.Dispose()
    Remove-Item $zipPath -Force
    exit 1
}
Write-Host "secret scan: clean ($($files.Count) files)"

foreach ($f in $files) {
    $rel = $f.FullName.Substring($RepoRoot.Length).TrimStart("\", "/") -replace "\\", "/"
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $f.FullName, "GlobalIntelligence/$rel"
    ) | Out-Null
}
$zip.Dispose()

# --- راستی‌آزمایی بسته: نبود موارد ممنوعه ---
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipRead = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$bad = @()
foreach ($e in $zipRead.Entries) {
    $n = $e.FullName
    if ($n -match "(^|/)\.env($|/)" -and $n -notmatch "\.env\.example$") { $bad += $n }
    elseif ($n -match "(^|/)\.git(/|$)") { $bad += $n }
    elseif ($n -match "(^|/)node_modules(/|$)") { $bad += $n }
    elseif ($n -match "(^|/)\.venv(/|$)") { $bad += $n }
    elseif ($n -match "__pycache__") { $bad += $n }
}
$zipRead.Dispose()
if ($bad.Count -gt 0) {
    Write-Host "ARCHIVE VERIFY FAILED:"
    $bad | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
    exit 1
}
Write-Host "archive verify: clean"
Write-Host "OK: $zipPath"
