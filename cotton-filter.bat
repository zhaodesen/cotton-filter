@echo off
chcp 65001 >nul
setlocal

REM === 配置 ===
set "SCRIPT=%~dp0cotton_filter.py"
set "LOG=%TEMP%\cotton-filter.log"

REM === 探测 Python ===
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo [错误] 未检测到 Python,请先安装 Python 3.9+ ^(勾选 Add to PATH^)
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM === 确保依赖已装 ===
%PY% -c "import pandas, openpyxl, xlrd" 2>nul
if errorlevel 1 (
    echo cotton-filter 首次运行,正在安装依赖 pandas openpyxl xlrd ...
    %PY% -m pip install --quiet pandas openpyxl xlrd
)

REM === 处理 ===
echo === %date% %time% === >> "%LOG%"
%PY% "%SCRIPT%" %* >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [错误] 处理失败,日志: "%LOG%"
    pause
    exit /b 1
)

endlocal
