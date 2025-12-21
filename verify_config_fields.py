#!/usr/bin/env python3
"""
直接验证配置类的字段定义
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def verify_config_fields():
    """验证配置字段"""
    print("=== 验证配置字段定义 ===")
    
    try:
        # 直接导入Settings类
        from infrastructure.config import Settings
        
        # 获取Settings类的所有字段
        print("\nSettings类定义的字段:")
        if hasattr(Settings, 'model_fields'):
            fields = Settings.model_fields
            for field_name, field_info in fields.items():
                print(f"  {field_name}: {field_info.annotation}")
        
        # 检查算法服务相关字段
        print("\n算法服务配置字段检查:")
        algorithm_fields = [
            'algorithm_config_path',
            'nl2sql_base_url', 
            'nl2sql_timeout',
            'clustering_api_url',
            'classification_api_url',
            'algorithm_api_timeout',
            'async_task_poll_interval',
            'async_task_max_wait_time',
            'stream_chunk_size',
            'stream_timeout',
            'mysql_host',
            'mysql_port',
            'mysql_database',
            'mysql_username',
            'mysql_password'
        ]
        
        for field_name in algorithm_fields:
            if hasattr(Settings, 'model_fields') and field_name in Settings.model_fields:
                print(f"✅ {field_name} 已定义")
            else:
                print(f"❌ {field_name} 未定义")
        
        # 尝试创建一个Settings实例
        print("\n尝试创建Settings实例:")
        try:
            settings = Settings()
            print("✅ Settings实例创建成功")
            
            # 验证算法配置字段的值
            print("\n算法配置字段的默认值:")
            for field_name in algorithm_fields:
                if hasattr(settings, field_name):
                    value = getattr(settings, field_name)
                    print(f"  {field_name}: {value}")
                else:
                    print(f"  {field_name}: <未找到>")
            
        except Exception as e:
            print(f"❌ Settings实例创建失败: {e}")
            import traceback
            traceback.print_exc()
        
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    verify_config_fields()
