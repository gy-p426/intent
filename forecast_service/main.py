"""
趋势分析与预测微服务入口
Forecast Microservice Entry Point
"""
import uvicorn
import logging
from config import get_settings


def setup_logging():
    """配置日志"""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    """主函数"""
    setup_logging()
    settings = get_settings()
    
    logger = logging.getLogger(__name__)
    logger.info(f"启动 {settings.service_name} v{settings.service_version}")
    logger.info(f"监听地址: {settings.service_host}:{settings.service_port}")
    
    uvicorn.run(
        "api.app:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
