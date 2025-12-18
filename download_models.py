#!/usr/bin/env python3
"""
HuggingFace模型下载脚本
用于下载意图识别服务所需的模型文件
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import json
import time

try:
    from huggingface_hub import snapshot_download, hf_hub_download
    from huggingface_hub.utils import HfHubHTTPError
except ImportError:
    print("❌ 缺少依赖包，请先安装：pip install huggingface_hub")
    sys.exit(1)


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelDownloader:
    """模型下载器"""
    
    def __init__(self, models_dir: str = "./models"):
        """
        初始化模型下载器
        
        Args:
            models_dir: 模型存储目录
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # 预定义的模型配置
        self.model_configs = {
            "text2vec-base-chinese": {
                "repo_id": "shibing624/text2vec-base-chinese",
                "description": "中文文本向量化模型（用于RAG检索）",
                "size_gb": 0.4,
                "required_files": [
                    "config.json",
                    "pytorch_model.bin",
                    "tokenizer.json",
                    "tokenizer_config.json",
                    "vocab.txt"
                ]
            },
            "paraphrase-MiniLM-L3-v2": {
                "repo_id": "sentence-transformers/paraphrase-MiniLM-L3-v2",
                "description": "轻量级英文文本向量化模型（用于测试）",
                "size_gb": 0.1,
                "required_files": [
                    "config.json",
                    "pytorch_model.bin",
                    "tokenizer.json",
                    "tokenizer_config.json",
                    "vocab.txt"
                ]
            }
        }
    
    def check_disk_space(self, required_gb: float) -> bool:
        """
        检查磁盘空间是否足够
        
        Args:
            required_gb: 需要的空间（GB）
            
        Returns:
            bool: 空间是否足够
        """
        try:
            import shutil
            free_bytes = shutil.disk_usage(self.models_dir).free
            free_gb = free_bytes / (1024**3)
            
            logger.info(f"可用磁盘空间: {free_gb:.1f} GB")
            logger.info(f"需要空间: {required_gb:.1f} GB")
            
            return free_gb >= required_gb
        except Exception as e:
            logger.warning(f"无法检查磁盘空间: {e}")
            return True  # 假设空间足够
    
    def is_model_downloaded(self, model_name: str) -> bool:
        """
        检查模型是否已下载
        
        Args:
            model_name: 模型名称
            
        Returns:
            bool: 模型是否已存在
        """
        model_path = self.models_dir / model_name
        
        if not model_path.exists():
            return False
        
        # 检查必需文件是否存在
        config = self.model_configs.get(model_name)
        if config:
            required_files = config.get("required_files", [])
            for file_name in required_files:
                if not (model_path / file_name).exists():
                    logger.warning(f"模型文件不完整，缺少: {file_name}")
                    return False
        
        return True
    
    def download_model(self, model_name: str, force: bool = False) -> Optional[str]:
        """
        下载指定模型
        
        Args:
            model_name: 模型名称
            force: 是否强制重新下载
            
        Returns:
            Optional[str]: 下载后的模型路径，失败返回None
        """
        if model_name not in self.model_configs:
            logger.error(f"未知的模型: {model_name}")
            logger.info(f"支持的模型: {list(self.model_configs.keys())}")
            return None
        
        config = self.model_configs[model_name]
        repo_id = config["repo_id"]
        description = config["description"]
        size_gb = config["size_gb"]
        
        local_path = self.models_dir / model_name
        
        # 检查是否已下载
        if not force and self.is_model_downloaded(model_name):
            logger.info(f"✅ 模型已存在: {local_path}")
            return str(local_path)
        
        # 检查磁盘空间
        if not self.check_disk_space(size_gb + 0.5):  # 额外0.5GB缓冲
            logger.error("❌ 磁盘空间不足")
            return None
        
        logger.info(f"📥 开始下载模型: {model_name}")
        logger.info(f"   描述: {description}")
        logger.info(f"   仓库: {repo_id}")
        logger.info(f"   大小: ~{size_gb} GB")
        logger.info(f"   路径: {local_path}")
        
        try:
            start_time = time.time()
            
            # 下载模型
            downloaded_path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_path),
                local_dir_use_symlinks=False,
                resume_download=True
            )
            
            end_time = time.time()
            download_time = end_time - start_time
            
            logger.info(f"✅ 模型下载完成: {downloaded_path}")
            logger.info(f"   耗时: {download_time:.1f} 秒")
            
            # 验证下载的文件
            if self.verify_model(model_name):
                logger.info("✅ 模型文件验证通过")
                return str(local_path)
            else:
                logger.error("❌ 模型文件验证失败")
                return None
                
        except HfHubHTTPError as e:
            logger.error(f"❌ 下载失败 (HTTP错误): {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            return None
    
    def verify_model(self, model_name: str) -> bool:
        """
        验证模型文件完整性
        
        Args:
            model_name: 模型名称
            
        Returns:
            bool: 验证是否通过
        """
        config = self.model_configs.get(model_name)
        if not config:
            return False
        
        model_path = self.models_dir / model_name
        required_files = config.get("required_files", [])
        
        missing_files = []
        for file_name in required_files:
            file_path = model_path / file_name
            if not file_path.exists():
                missing_files.append(file_name)
            else:
                # 检查文件大小（不能为0）
                if file_path.stat().st_size == 0:
                    missing_files.append(f"{file_name} (空文件)")
        
        if missing_files:
            logger.error(f"缺少文件: {missing_files}")
            return False
        
        return True
    
    def download_all_models(self, force: bool = False) -> Dict[str, bool]:
        """
        下载所有预定义的模型
        
        Args:
            force: 是否强制重新下载
            
        Returns:
            Dict[str, bool]: 各模型的下载结果
        """
        results = {}
        
        logger.info(f"📦 开始下载所有模型 (共 {len(self.model_configs)} 个)")
        
        for model_name in self.model_configs:
            logger.info(f"\n{'='*60}")
            result = self.download_model(model_name, force)
            results[model_name] = result is not None
        
        return results
    
    def list_models(self):
        """列出所有可用的模型"""
        logger.info("📋 可用模型列表:")
        logger.info("="*60)
        
        for model_name, config in self.model_configs.items():
            status = "✅ 已下载" if self.is_model_downloaded(model_name) else "❌ 未下载"
            logger.info(f"模型: {model_name}")
            logger.info(f"  状态: {status}")
            logger.info(f"  描述: {config['description']}")
            logger.info(f"  仓库: {config['repo_id']}")
            logger.info(f"  大小: ~{config['size_gb']} GB")
            logger.info(f"  路径: {self.models_dir / model_name}")
            logger.info("")
    
    def clean_model(self, model_name: str) -> bool:
        """
        清理指定模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            bool: 清理是否成功
        """
        if model_name not in self.model_configs:
            logger.error(f"未知的模型: {model_name}")
            return False
        
        model_path = self.models_dir / model_name
        
        if not model_path.exists():
            logger.info(f"模型不存在: {model_path}")
            return True
        
        try:
            import shutil
            shutil.rmtree(model_path)
            logger.info(f"✅ 模型已清理: {model_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 清理失败: {e}")
            return False
    
    def generate_config_update(self) -> str:
        """
        生成配置文件更新建议
        
        Returns:
            str: 配置更新内容
        """
        config_updates = []
        
        for model_name in self.model_configs:
            if self.is_model_downloaded(model_name):
                local_path = f"./models/{model_name}"
                config_updates.append(f"# 使用本地模型: {model_name}")
                config_updates.append(f'embedding_model: str = Field(')
                config_updates.append(f'    default="{local_path}",')
                config_updates.append(f'    description="文本向量化模型名称"')
                config_updates.append(f')')
                config_updates.append("")
        
        return "\n".join(config_updates)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="HuggingFace模型下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python download_models.py --list                    # 列出所有模型
  python download_models.py --download text2vec-base-chinese  # 下载指定模型
  python download_models.py --download-all            # 下载所有模型
  python download_models.py --clean text2vec-base-chinese     # 清理指定模型
        """
    )
    
    parser.add_argument(
        "--models-dir",
        default="./models",
        help="模型存储目录 (默认: ./models)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用模型"
    )
    
    parser.add_argument(
        "--download",
        metavar="MODEL_NAME",
        help="下载指定模型"
    )
    
    parser.add_argument(
        "--download-all",
        action="store_true",
        help="下载所有模型"
    )
    
    parser.add_argument(
        "--clean",
        metavar="MODEL_NAME",
        help="清理指定模型"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新下载（即使已存在）"
    )
    
    parser.add_argument(
        "--config",
        action="store_true",
        help="生成配置文件更新建议"
    )
    
    args = parser.parse_args()
    
    # 创建下载器
    downloader = ModelDownloader(args.models_dir)
    
    # 执行操作
    if args.list:
        downloader.list_models()
    
    elif args.download:
        result = downloader.download_model(args.download, args.force)
        if result:
            logger.info(f"🎉 模型下载成功: {result}")
        else:
            logger.error("💥 模型下载失败")
            sys.exit(1)
    
    elif args.download_all:
        results = downloader.download_all_models(args.force)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        logger.info(f"\n📊 下载结果汇总:")
        for model_name, success in results.items():
            status = "✅ 成功" if success else "❌ 失败"
            logger.info(f"  {model_name}: {status}")
        
        logger.info(f"\n总计: {success_count}/{total_count} 成功")
        
        if success_count < total_count:
            sys.exit(1)
    
    elif args.clean:
        success = downloader.clean_model(args.clean)
        if not success:
            sys.exit(1)
    
    elif args.config:
        config_content = downloader.generate_config_update()
        if config_content:
            logger.info("📝 配置文件更新建议:")
            logger.info("="*60)
            print(config_content)
        else:
            logger.info("没有已下载的模型，无需更新配置")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()