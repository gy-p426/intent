#!/usr/bin/env python3
"""
检查服务是否在运行
"""
import requests
import time

def check_service(base_url="http://localhost:8000", max_retries=5):
    """检查服务是否在运行"""
    print(f"检查服务状态: {base_url}")
    
    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 服务正在运行")
                print(f"   服务: {data.get('service')}")
                print(f"   版本: {data.get('version')}")
                print(f"   状态: {data.get('status')}")
                return True
            else:
                print(f"⚠️ 服务响应异常: HTTP {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ 连接失败 (尝试 {i+1}/{max_retries})")
            if i < max_retries - 1:
                print("   等待 2 秒后重试...")
                time.sleep(2)
        except Exception as e:
            print(f"❌ 检查失败: {e}")
            
    print("❌ 服务未运行或无法访问")
    print("\n请先启动服务:")
    print("D:\\Anaconda\\envs\\intent\\python.exe main.py")
    return False

if __name__ == "__main__":
    check_service()