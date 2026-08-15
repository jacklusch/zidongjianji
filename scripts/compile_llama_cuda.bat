@echo off
rem ============================================================
rem 编译 CUDA 版 llama-cpp-python（Windows）
rem 前置：Visual Studio Build Tools/Community + CUDA Toolkit + cmake
rem 用法：scripts\compile_llama_cuda.bat
rem 说明：abetlen 官方不提供 Windows CUDA 预编译 wheel，
rem       需从源码编译。完成后 python 可用 GPU 推理 VLM。
rem ============================================================
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 VS2022 Community，请先安装并核对路径
    exit /b 1
)
set CMAKE_ARGS=-DGGML_CUDA=on
set FORCE_CMAKE=1
set CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9
if not exist "%CUDA_PATH%\bin\nvcc.exe" (
    echo [WARN] 未在默认路径找到 CUDA v12.9，请按需调整 CUDA_PATH
)
cd /d "%~dp0\.."
echo 开始编译 CUDA 版 llama-cpp-python（约 30-60 分钟）...
venv\Scripts\python.exe -m pip install llama-cpp-python --no-cache-dir --force-reinstall --no-deps
if errorlevel 1 (
    echo [ERROR] 编译失败，请检查 VS/CUDA/cmake 环境
    exit /b 1
)
echo 编译完成！llama-cpp-python 已启用 CUDA GPU 推理
venv\Scripts\python.exe -c "from llama_cpp import llama_cpp; print('GPU offload:', llama_cpp.llama_supports_gpu_offload())"
