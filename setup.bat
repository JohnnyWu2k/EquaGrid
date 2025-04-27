@echo off
setlocal

pip install -r requirements.txt

set /p SIZE="size:"
set /p IP="IP:"
set /p PORT="Port:"

(
  echo SIZE=%SIZE%
  echo IP=%IP%
  echo PORT=%PORT%
) > "%~dp0config.txt"
