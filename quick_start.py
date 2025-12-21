#!/usr/bin/env python3
"""
快速开始脚本
一键安装依赖、下载模型、配置环境
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        logger.error("❌ 需要Python 3.8或更高版本")
        return False
    
    logger.info(f"✅ Python版本: {sys.version}")
    return True


def install_dependencies():
    """安装依赖"""
    logger.info("📦 安装项目依赖...")
    
    try:
        # 运行依赖安装脚本
        result = subprocess.run([sys.executable, "install_dependencies.py"], check=True)
        logger.info("✅ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ 依赖安装失败: {e}")
        return False


def setup_environment():
    """设置环境配置"""
    logger.info("⚙️  配置环境变量...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        logger.info("✅ .env 文件已存在")
        return True
    
    if env_example.exists():
        try:
            # 复制示例配置文件
            import shutil
            shutil.copy(env_example, env_file)
            logger.info("✅ 已创建 .env 文件（从 .env.example 复制）")
            logger.warning("⚠️  请编辑 .env 文件，设置必需的配置项（如 ARK_API_KEY）")
            return True
        except Exception as e:
            logger.error(f"❌ 创建 .env 文件失败: {e}")
            return False
    else:
        logger.warning("⚠️  .env.example 文件不存在，请手动创建 .env 文件")
        return True


def check_knowledge_base():
    """检查知识库文件"""
    logger.info("📚 检查知识库文件...")
    
    kb_file = Path("intent.txt")
    
    if kb_file.exists():
        logger.info("✅ 知识库文件 intent.txt 已存在")
        return True
    else:
        logger.warning("⚠️  知识库文件 intent.txt 不存在")
        logger.info("💡 创建示例知识库文件...")
        
        try:
            # 创建示例知识库
            sample_kb = """text,intent
请你根据消费次数帮我将用户分为两类,classify
我想看看明天的销售预测,predict
帮我分析一下用户的购买行为,classify
能否预测下个月的收入情况,predict
我需要对客户进行分组管理,classify
根据历史数据预测未来趋势,predict"""
            
            with open(kb_file, 'w', encoding='utf-8') as f:
                f.write(sample_kb)
            
            logger.info("✅ 已创建示例知识库文件")
            return True
        except Exception as e:
            logger.error(f"❌ 创建知识库文件失败: {e}")
            return False


def download_models():
    """下载模型"""
    logger.info("🤖 下载文本向量化模型...")
    
    try:
        # 检查模型下载脚本是否存在
        if not Path("download_models.py").exists():
            logger.warning("⚠️  模型下载脚本不存在，跳过模型下载")
            return True
        
        # 运行模型下载
        result = subprocess.run([
            sys.executable, "download_models.py", 
            "--download", "text2vec-base-chinese"
        ], check=True, capture_output=True, text=True)
        
        logger.info("✅ 模型下载完成")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.warning("⚠️  模型下载失败，将使用在线模式")
        logger.debug(f"错误详情: {e.stderr}")
        return True  # 模型下载失败不影响整体流程


def test_service():
    """测试服务启动"""
    logger.info("🧪 测试服务启动...")
    
    try:
        # 尝试导入主要模块
        import fastapi
        import uvicorn
        logger.info("✅ 核心依赖导入成功")
        
        # 检查配置
        from infrastructure.config import get_settings
        settings = get_settings()
        logger.info(f"✅ 配置加载成功，服务端口: {settings.service_port}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 服务测试失败: {e}")
        return False


def print_next_steps():
    """打印后续步骤"""
    logger.info("\n" + "="*60)
    logger.info("🎉 快速开始完成！")
    logger.info("="*60)
    logger.info("📋 后续步骤:")
    logger.info("")
    logger.info("1. 编辑配置文件:")
    logger.info("   vim .env")
    logger.info("   # 设置 ARK_API_KEY 等必需配置")
    logger.info("")
    logger.info("2. 启动服务:")
    logger.info("   python main.py")
    logger.info("")
    logger.info("3. 测试服务:")
    logger.info("   curl http://localhost:8000/health")
    logger.info("")
    logger.info("4. 测试意图识别:")
    logger.info('   curl -X POST http://localhost:8000/api/v1/intent/recognize \\')
    logger.info('     -H "Content-Type: application/json" \\')
    logger.info('     -d \'{"question": "请帮我分类用户"}\'')
    logger.info("")
    logger.info("📖 更多信息请查看:")
    logger.info("   - README.md: 完整文档")
    logger.info("   - MODEL_DOWNLOAD_GUIDE.md: 模型下载指南")
    logger.info("   - DEPLOYMENT.md: 部署指南")


def main():
    """主函数"""
    logger.info("🚀 意图识别服务快速开始...")
    logger.info("="*60)
    
    # 检查步骤
    steps = [
        ("检查Python版本", check_python_version),
        ("安装项目依赖", install_dependencies),
        ("配置环境变量", setup_environment),
        ("检查知识库文件", check_knowledge_base),
        ("下载向量化模型", download_models),
        ("测试服务配置", test_service)
    ]
    
    failed_steps = []
    
    for step_name, step_func in steps:
        logger.info(f"\n📋 {step_name}...")
        try:
            if not step_func():
                failed_steps.append(step_name)
        except Exception as e:
            logger.error(f"❌ {step_name} 执行异常: {e}")
            failed_steps.append(step_name)
    
    # 结果汇总
    if failed_steps:
        logger.error(f"\n💥 以下步骤失败: {failed_steps}")
        logger.error("请检查错误信息并手动处理")
        sys.exit(1)
    else:
        print_next_steps()


if __name__ == "__main__":
    main()