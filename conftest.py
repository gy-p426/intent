# -*- coding: utf-8 -*-
"""
Pytest configuration for all tests.

设置测试环境，避免配置验证失败。
"""

import os
import sys

# 设置测试环境变量，必须在任何导入之前
os.environ['ARK_API_KEY'] = 'test_key_for_testing'
os.environ['TESTING'] = 'true'

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
