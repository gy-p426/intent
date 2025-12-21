#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键启动脚本
同时启动后端服务和前端测试页面
"""

import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           算法集成服务 - 一键启动脚本                        ║
║                                                              ║
║        Algorithm Integration Service Launcher                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print("需要Python 3.8或更高版本")
        print(f"   当前版本: {sys.version}")
        return False
    print(f"Python版本检查通过: {sys.version.split()[0]}")
    return True

def check_dependencies():
    """检查依赖包"""
    required_packages = ['fastapi', 'uvicorn', 'pydantic']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"[OK] {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"[FAIL] {package} 未安装")
    
    if missing_packages:
        print(f"\n缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def start_backend():
    """启动后端服务"""
    print("\n" + "="*60)
    print("启动后端服务...")
    print("="*60)
    
    try:
        # 启动后端服务（不阻塞）
        backend_process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("等待后端服务启动...")
        time.sleep(3)  # 等待服务启动
        
        # 检查进程是否还在运行
        if backend_process.poll() is None:
            print("[OK] 后端服务已启动")
            print("后端地址: http://localhost:8000")
            print("API文档: http://localhost:8000/docs")
            return backend_process
        else:
            stdout, stderr = backend_process.communicate()
            print("[FAIL] 后端服务启动失败")
            if stderr:
                print(f"错误信息: {stderr}")
            return None
            
    except Exception as e:
        print(f"[ERROR] 启动后端服务时出错: {e}")
        return None

def start_frontend():
    """启动前端服务"""
    print("\n" + "="*60)
    print("启动前端测试页面...")
    print("="*60)
    
    try:
        frontend_dir = Path(__file__).parent / "frontend"
        
        # 启动前端服务（不阻塞）
        frontend_process = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("等待前端服务启动...")
        time.sleep(2)  # 等待服务启动
        
        # 检查进程是否还在运行
        if frontend_process.poll() is None:
            print("[OK] 前端服务已启动")
            print("前端地址: http://localhost:3000")
            print("测试页面: http://localhost:3000/index.html")
            
            # 自动打开浏览器
            try:
                time.sleep(1)
                webbrowser.open('http://localhost:3000/index.html')
                print("已自动打开浏览器")
            except Exception as e:
                print(f"无法自动打开浏览器: {e}")
            
            return frontend_process
        else:
            stdout, stderr = frontend_process.communicate()
            print("[FAIL] 前端服务启动失败")
            if stderr:
                print(f"错误信息: {stderr}")
            return None
            
    except Exception as e:
        print(f"[ERROR] 启动前端服务时出错: {e}")
        return None

def print_usage_info():
    """打印使用说明"""
    info = """
╔══════════════════════════════════════════════════════════════╗
║                      启动成功！                              ║
╚══════════════════════════════════════════════════════════════╝

服务信息:
   • 后端服务: http://localhost:8000
   • API文档:  http://localhost:8000/docs
   • 前端页面: http://localhost:3000/index.html

快速开始:
   1. 浏览器会自动打开测试页面
   2. 在"健康检查"标签页验证服务状态
   3. 在"意图识别"标签页测试意图识别
   4. 在"算法执行"标签页测试算法功能
   5. 在"流式执行"标签页查看实时执行过程

功能特性:
   [OK] 健康检查 - 检查服务和组件状态
   [OK] 意图识别 - 测试自然语言理解
   [OK] 算法执行 - 完整算法流程测试
   [OK] 流式响应 - 实时查看执行进度
   [OK] 任务管理 - 异步任务监控
   [OK] 服务指标 - 性能监控和分析

停止服务:
   按 Ctrl+C 停止所有服务

日志查看:
   • 后端日志会实时显示在控制台
   • 前端日志可在浏览器控制台查看

提示:
   • 确保端口 8000 和 3000 未被占用
   • 如需修改端口，请编辑配置文件
   • 遇到问题请查看 frontend/README.md

════════════════════════════════════════════════════════════════
    """
    print(info)

def main():
    """主函数"""
    print_banner()
    
    # 检查环境
    print("检查运行环境...")
    if not check_python_version():
        sys.exit(1)
    
    print("\n检查依赖包...")
    if not check_dependencies():
        print("\n提示: 请先安装依赖包后再运行此脚本")
        sys.exit(1)
    
    # 启动后端服务
    backend_process = start_backend()
    if not backend_process:
        print("\n[FAIL] 后端服务启动失败，无法继续")
        sys.exit(1)
    
    # 启动前端服务
    frontend_process = start_frontend()
    if not frontend_process:
        print("\n[FAIL] 前端服务启动失败")
        print("后端服务仍在运行，您可以手动访问 http://localhost:8000/docs")
        
        # 等待用户中断
        try:
            print("\n按 Ctrl+C 停止后端服务...")
            backend_process.wait()
        except KeyboardInterrupt:
            print("\n\n正在停止服务...")
            backend_process.terminate()
            backend_process.wait()
        
        sys.exit(1)
    
    # 打印使用说明
    print_usage_info()
    
    # 等待用户中断
    try:
        print("服务运行中... (按 Ctrl+C 停止)")
        print("="*60 + "\n")
        
        # 持续运行，直到用户中断
        while True:
            time.sleep(1)
            
            # 检查进程是否还在运行
            if backend_process.poll() is not None:
                print("\n后端服务已停止")
                break
            if frontend_process.poll() is not None:
                print("\n前端服务已停止")
                break
                
    except KeyboardInterrupt:
        print("\n\n收到停止信号，正在关闭服务...")
    
    # 清理进程
    print("清理进程...")
    
    if backend_process and backend_process.poll() is None:
        print("   停止后端服务...")
        backend_process.terminate()
        try:
            backend_process.wait(timeout=5)
            print("   [OK] 后端服务已停止")
        except subprocess.TimeoutExpired:
            print("   强制终止后端服务...")
            backend_process.kill()
    
    if frontend_process and frontend_process.poll() is None:
        print("   停止前端服务...")
        frontend_process.terminate()
        try:
            frontend_process.wait(timeout=5)
            print("   [OK] 前端服务已停止")
        except subprocess.TimeoutExpired:
            print("   强制终止前端服务...")
            frontend_process.kill()
    
    print("\n[OK] 所有服务已停止")
    print("感谢使用算法集成服务！\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] 发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)