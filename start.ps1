$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
Set-Location $PSScriptRoot
& ./.venv/Scripts/python.exe -m uvicorn docagent.api:app --host 127.0.0.1 --port 8011
