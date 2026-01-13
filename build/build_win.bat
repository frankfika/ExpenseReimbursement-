@echo off
chcp 65001 >nul
REM 报销助手 - Windows 打包脚本

echo ====================================
echo 报销助手 - Windows 打包工具
echo ====================================
echo.

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

REM 读取版本号
set /p VERSION=<VERSION
set VERSION_TAG=v%VERSION%

echo 版本: %VERSION_TAG%
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

echo [1/4] 安装依赖...
python -m pip install -r requirements.txt -q --user

echo.
echo [2/4] 清理旧的构建文件...
if exist "build\build" rmdir /s /q "build\build"
if exist "dist" rmdir /s /q "dist"

echo.
echo [3/4] 开始打包...
python -m PyInstaller --clean build/build_win.spec

echo.
if exist "dist\ExpenseHelper\ExpenseHelper.exe" (
    echo [4/4] 打包成功！
    echo.

    REM 创建 releases 目录
    set RELEASE_DIR=releases\%VERSION_TAG%
    if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"

    REM 复制整个目录
    echo 复制到 releases 目录...
    xcopy /s /e /i /y "dist\ExpenseHelper" "%RELEASE_DIR%\ExpenseHelper"

    REM 创建 ZIP 文件（如果有 7z）
    where 7z >nul 2>&1
    if not errorlevel 1 (
        echo 创建 ZIP 压缩包...
        7z a -tzip "%RELEASE_DIR%\ExpenseHelper-%VERSION%-win.zip" "dist\ExpenseHelper\*"
        echo.
        echo ZIP: %RELEASE_DIR%\ExpenseHelper-%VERSION%-win.zip
    )

    echo.
    echo ====================================
    echo 完成！
    echo ====================================
    echo.
    echo 版本: %VERSION_TAG%
    echo 输出: %RELEASE_DIR%\ExpenseHelper\ExpenseHelper.exe
    echo.
) else (
    echo [错误] 打包失败，请检查错误信息
)

pause
