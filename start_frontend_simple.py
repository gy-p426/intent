#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的前端启动脚本 - 兼容Windows
"""

import os
import sys
import http.server
import socketserver
import webbrowser
from pathlib import Path

def start_frontend_server(port=3000):
    """启动前端服务器"""
    
    # 切换到frontend目录
    frontend_dir = Path(__file__).parent / "frontend"
    if not frontend_dir.exists():
        print(f"错误: frontend目录不存在: {frontend_dir}")
        return False
    
    os.chdir(frontend_dir)
    
    print("=" * 50)
    print("算法集成服务测试前端")
    print("=" * 50)
    print(f"服务目录: {frontend_dir}")
    print(f"服务地址: http://localhost:{port}")
    print(f"测试页面: http://localhost:{port}/index.html")
    print(f"后端服务: http://localhost:8000")
    print()
    print("使用说明:")
    print("1. 确保后端服务已在 http://localhost:8000 运行")
    print("2. 浏览器会自动打开测试页面")
    print("3. 使用各个标签页测试不同的API功能")
    print("4. 按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    try:
        # 创建支持CORS的请求处理器
        class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                super().end_headers()
            
            def do_OPTIONS(self):
                self.send_response(200)
                self.end_headers()
        
        # 启动服务器
        with socketserver.TCPServer(("", port), CORSHTTPRequestHandler) as httpd:
            print(f"前端服务器已启动在端口 {port}")
            
            # 自动打开浏览器
            try:
                webbrowser.open(f'http://localhost:{port}/index.html')
                print("已自动打开浏览器")
            except Exception as e:
                print(f"无法自动打开浏览器: {e}")
                print(f"请手动访问: http://localhost:{port}/index.html")
            
            print("\n开始提供服务... (按 Ctrl+C 停止)")
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n\n用户中断，正在关闭服务器...")
        return True
    except OSError as e:
        if "Address already in use" in str(e) or e.errno == 10048:  # Windows错误码
            print(f"端口 {port} 已被占用，请尝试其他端口")
            print(f"使用方法: python start_frontend_simple.py")
        else:
            print(f"启动服务器失败: {e}")
        return False
    except Exception as e:
        print(f"服务器运行错误: {e}")
        return False

if __name__ == "__main__":
    # 获取端口号参数
    port = 3000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("无效的端口号，使用默认端口 3000")
            port = 3000
    
    success = start_frontend_server(port)
    if success:
        print("前端服务器已正常关闭")
    else:
        print("前端服务器启动失败")
        sys.exit(1)