# Builds the release zip: dist\LiveCaptions-<version>-win64.zip
#   - Live Captions.exe (launcher, compiled with the C# compiler that comes with Windows)
#   - the program, the lock file and the docs
#   - tools\uv.exe (installs Python and the packages on first run)
# Usage:  powershell -ExecutionPolicy Bypass -File tools\build_release.ps1 -Version v0.2.0 [-UvExe C:\path\uv.exe]
param(
    [string]$Version = "dev",
    [string]$UvExe = "",           # copy this uv.exe instead of downloading it
    [string]$UvVersion = "0.11.7"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $root "dist"
$stage = Join-Path $dist "LiveCaptions"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Force $stage | Out-Null

# 1. launcher
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "C# compiler not found: $csc" }
& $csc -nologo -target:winexe -optimize+ "-win32icon:$root\live_captions\assets\app.ico" "-out:$stage\Live Captions.exe" `
    -r:System.Windows.Forms.dll -r:System.Drawing.dll "$root\launcher\Launcher.cs"
if ($LASTEXITCODE -ne 0) { throw "compiling the launcher failed" }

# 2. program and docs
Copy-Item -Recurse "$root\live_captions" "$stage\live_captions"
Get-ChildItem -Recurse -Directory -Filter __pycache__ "$stage\live_captions" | Remove-Item -Recurse -Force
foreach ($f in @("pyproject.toml", "uv.lock", ".python-version", "README.md", "README_TH.md", "LICENSE",
                 "config.example.toml", "terms.example.txt",
                 "start_live_captions.bat", "rehearse.bat", "download_models.bat", "setup.bat")) {
    if (Test-Path "$root\$f") { Copy-Item "$root\$f" "$stage\$f" }
}
New-Item -ItemType Directory -Force "$stage\scripts", "$stage\tools" | Out-Null
Copy-Item "$root\scripts\find_python.bat" "$stage\scripts\"
Set-Content -Encoding ascii "$stage\live_captions\VERSION" $Version

# 3. uv
if ($UvExe) {
    Copy-Item $UvExe "$stage\tools\uv.exe"
} else {
    $zip = Join-Path $dist "uv.zip"
    $url = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
    Write-Output "downloading $url"
    Invoke-WebRequest -UseBasicParsing $url -OutFile $zip
    Expand-Archive $zip (Join-Path $dist "uv")
    Copy-Item (Join-Path $dist "uv\uv.exe") "$stage\tools\uv.exe"
    Remove-Item -Recurse -Force $zip, (Join-Path $dist "uv")
}

# 4. zip
$out = Join-Path $dist "LiveCaptions-$Version-win64.zip"
Compress-Archive -Path $stage -DestinationPath $out
$mb = [math]::Round((Get-Item $out).Length / 1MB, 1)
Write-Output "built $out ($mb MB)"
