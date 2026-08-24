@echo off
setlocal
cd /d "%~dp0"

where /q py
if errorlevel 1 goto :try_python
py -3 rr_optimizer.py ui %*
goto :end

:try_python
where /q python
if errorlevel 1 goto :python_missing
python rr_optimizer.py ui %*
goto :end

:python_missing
echo.
echo [RR] 未找到 Python 3。
echo 请先从 https://www.python.org/downloads/ 安装 Python 3.11 或更高版本。
echo 安装时请勾选 Add Python to PATH。
echo.
pause

:end
endlocal
