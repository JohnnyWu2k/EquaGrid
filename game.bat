@echo off
setlocal enabledelayedexpansion

:main

for /f "usebackq tokens=1* delims==" %%K in ("config.txt") do (
    set "%%K=%%L"
)

set SIZE=%SIZE%
set IP=%ip%
set PORT=%PORT%
set choice = 0
echo ================================
echo   Select:
echo   [1] Server 
echo   [2] Client 
echo   [3] Config
echo ================================
set /p choice="enter the number:"
if "%choice%" == "1" goto :server
if "%choice%" == "2" goto :client
if "%choice%" == "3" goto :config
exit

:server
cls
pushd "%~dp0\src"
python game.py server %PORT% %SIZE%
goto :eof

:client
cls
pushd "%~dp0\src"
python game.py client %IP% %PORT%
goto :eof

:config

set /p SIZE="size:"
set /p IP="IP:"
set /p PORT="Port:"

(
  echo SIZE=%SIZE%
  echo IP=%IP%
  echo PORT=%PORT%
) > "%~dp0config.txt"
goto :main