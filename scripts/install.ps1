$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path "venv\Scripts\python.exe")) {
    py -3.11 -m venv venv
    if (-not $?) { python -m venv venv }
}
$py = Join-Path $root "venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
# FFmpeg：PATH 或 bin\ffmpeg
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ff -and -not (Test-Path "bin\ffmpeg\bin\ffmpeg.exe") -and -not (Test-Path "bin\ffmpeg\ffmpeg.exe")) {
    New-Item -ItemType Directory -Path "bin" -Force | Out-Null
    $zip = Join-Path $env:TEMP "ffmpeg.zip"
    Invoke-WebRequest -Uri "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "bin" -Force
    $extracted = Get-ChildItem "bin" -Directory | Where-Object Name -like "ffmpeg-*" | Select-Object -First 1
    Move-Item $extracted.FullName "bin\ffmpeg" -Force
}
if (-not (Test-Path "config.yaml")) { Copy-Item "config.yaml.example" "config.yaml" }
"安装完成。运行 scripts\start.ps1 开始使用。"