#!/usr/bin/env python3
"""
检查 Nacos 服务器连接状态
"""
import socket
import requests
from infrastructure.config import get_settings

def check_nacos_connection():
    """检查 Nacos 服务器连接状态"""
    settings = get_settings()
    server_addr = settings.nacos_server_addr
    
    try:
        # 解析服务器地址
        if ':' in server_addr:
            host, port = server_addr.split(':', 1)
            port = int(port)
        else:
            host = server_addr
            port = 8848
        
        print(f"检查 Nacos 服务器连接: {host}:{port}")
        
        # 1. 检查端口是否可达
        print("1. 检查端口连通性...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result != 0:
            print(f"❌ 无法连接到 {host}:{port}")
            print("可能的原因:")
            print("- Nacos 服务器未启动")
            print("- 防火墙阻止连接")
            print("- 服务器地址配置错误")
            return False
        else:
            print(f"✅ 端口 {host}:{port} 可达")
        
        # 2. 检查 Nacos HTTP API
        print("2. 检查 Nacos HTTP API...")
        try:
            url = f"http://{host}:{port}/nacos/v1/ns/operator/servers"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("✅ Nacos HTTP API 正常")
                return True
            else:
                print(f"⚠️ Nacos HTTP API 返回状态码: {response.status_code}")
                return False
        except requests.RequestException as e:
            print(f"❌ Nacos HTTP API 请求失败: {e}")
            return False
            
    except Exception as e:
        print(f"❌ 检查过程中出现错误: {e}")
        return False

if __name__ == "__main__":
    print("=== Nacos 连接检查工具 ===")
    success = check_nacos_connection()
    
    if success:
        print("\n✅ Nacos 服务器连接正常")
    else:
        print("\n❌ Nacos 服务器连接失败")
        print("\n解决方案:")
        print("1. 启动 Nacos 服务器:")
        print("   - 下载 Nacos: https://github.com/alibaba/nacos/releases")
        print("   - 启动命令: sh startup.sh -m standalone (Linux/Mac)")
        print("   - 启动命令: startup.cmd -m standalone (Windows)")
        print("2. 检查配置文件 .env 中的 NACOS_SERVER_ADDR 设置")
        print("3. 如果不需要服务注册，可以在代码中禁用 Nacos 功能")