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
# GPU 检测：有 nvidia-smi 则装 CUDA 版模型依赖
$gpu = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($gpu) {
    Write-Host "检测到 NVIDIA GPU，安装 CUDA 版模型依赖..."
    & $py -m pip install "torch==2.13.0+cu121" --index-url https://download.pytorch.org/whl/cu121
    & $py -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
} else {
    Write-Host "未检测到 NVIDIA GPU，安装 CPU 版模型依赖..."
    & $py -m pip install -r requirements-models.txt
}
& $py -m pip install -r requirements-models.txt  # 其余模型依赖（funasr/sentence-transformers 等）
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