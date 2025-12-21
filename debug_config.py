#!/usr/bin/env python3
"""
Debug configuration loading
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from infrastructure.config import get_settings
    
    settings = get_settings()
    
    print("Available settings attributes:")
    for attr in dir(settings):
        if not attr.startswith('_'):
            value = getattr(settings, attr)
            if not callable(value):
                print(f"  {attr}: {value}")
    
    print(f"\nHas algorithm_config_path: {hasattr(settings, 'algorithm_config_path')}")
    if hasattr(settings, 'algorithm_config_path'):
        print(f"algorithm_config_path value: {settings.algorithm_config_path}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()