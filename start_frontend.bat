@echo off
chcp 65001 >nul
title 算法集成服务测试前端

echo ================================================
echo           算法集成服务测试前端
echo ================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

REM 检查后端服务是否运行
echo 检查后端服务状态...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo 警告: 后端服务可能未运行
    echo 请确保后端服务已在 http://localhost:8000 启动
    echo.
    echo 启动后端服务命令: python main.py
    echo.
    set /p choice="是否继续启动前端? (y/n): "
    if /i not "%choice%"=="y" (
        echo 已取消启动
        pause
        exit /b 0
    )
) else (
    echo 后端服务运行正常
)

echo.
echo 启动前端测试页面...
echo 浏览器将自动打开 http://localhost:3000/index.html
echo 按 Ctrl+C 停止服务器
echo.

REM 启动前端服务器
python start_frontend_simple.py

echo.
echo 前端服务器已关闭
pause