@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM === 配置 ===
set "SCRIPT=%~dp0cotton_filter.py"
set "LOG=%TEMP%\cotton_filter.log"

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
%PY% -c "import pandas, openpyxl" 2>nul
if errorlevel 1 (
    echo 首次运行,正在安装依赖 pandas openpyxl ...
    %PY% -m pip install --quiet pandas openpyxl
)

REM === 处理 ===
echo === %date% %time% === >> "%LOG%"

if "%~1"=="" (
    REM 双击启动,弹出选择对话框
    for /f "delims=" %%F in ('powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $f=New-Object System.Windows.Forms.OpenFileDialog; $f.Multiselect=$true; $f.Filter='Excel|*.xlsx;*.xls'; if($f.ShowDialog() -eq 'OK'){$f.FileNames -join '|'}"') do set "PICKED=%%F"
    if not defined PICKED exit /b 0
    for %%F in ("!PICKED:|=" "!") do (
        %PY% "%SCRIPT%" %%F >> "%LOG%" 2>&1
        set "LAST=%%~dpF"
    )
) else (
    for %%F in (%*) do (
        %PY% "%SCRIPT%" "%%~F" >> "%LOG%" 2>&1
        set "LAST=%%~dpF"
    )
)

REM === 打开结果文件夹 ===
if exist "!LAST!筛选结果" start "" "!LAST!筛选结果"

REM === 通知(Windows 10+ toast) ===
powershell -NoProfile -Command "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]>$null; $t='<toast><visual><binding template=\"ToastText02\"><text id=\"1\">棉花筛选 完成</text><text id=\"2\">已生成结果文件</text></binding></visual></toast>'; $x=New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($t); [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('棉花筛选').Show([Windows.UI.Notifications.ToastNotification]::new($x))" 2>nul

endlocal
