$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& "venv\Scripts\python.exe" -m app.main --help
"提示：python -m app.main index materials  # 建立素材索引"