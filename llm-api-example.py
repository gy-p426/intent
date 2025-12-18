"""
LLM模块测试示例
用于验证LLM客户端和模块的基本功能
"""
import asyncio
import logging
from llm import LLMClient, LLMModule
from infrastructure.config import get_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_llm_client():
    """测试LLM客户端基本功能"""
    logger.info("=== 测试LLM客户端 ===")
    
    try:
        # 加载配置
        settings = get_settings()
        
        # 创建LLM客户端
        client = LLMClient(
            api_key=settings.ark_api_key,
            model=settings.ark_model,
            timeout=settings.ark_timeout,
            max_retries=settings.llm_max_retries,
            retry_delay=settings.llm_retry_delay
        )
        
        # 测试简单对话
        messages = [
            {"role": "system", "content": "你是一个有帮助的助手。"},
            {"role": "user", "content": "请用一句话介绍Python编程语言。"}
        ]
        
        logger.info("发送测试请求...")
        response = await client.chat_completion(messages)
        
        logger.info(f"收到响应: {response}")
        logger.info("✓ LLM客户端测试通过")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ LLM客户端测试失败: {str(e)}")
        return False


async def test_llm_module():
    """测试LLM模块意图分类功能"""
    logger.info("\n=== 测试LLM模块 ===")
    
    try:
        # 加载配置
        settings = get_settings()
        
        # 创建LLM客户端和模块
        client = LLMClient(
            api_key=settings.ark_api_key,
            model=settings.ark_model,
            timeout=settings.ark_timeout,
            max_retries=settings.llm_max_retries,
            retry_delay=settings.llm_retry_delay
        )
        
        llm_module = LLMModule(client)
        
        # 模拟候选微服务
        candidates = [
            {
                "intent": "classify",
                "text": "请你根据消费次数帮我将用户分为两类",
                "score": 0.95
            },
            {
                "intent": "classify",
                "text": "帮我对客户进行分类",
                "score": 0.92
            },
            {
                "intent": "predict",
                "text": "预测明天的销售额",
                "score": 0.65
            },
            {
                "intent": "analyze",
                "text": "分析用户行为数据",
                "score": 0.60
            }
        ]
        
        # 测试意图分类
        question = "请你根据消费次数帮我将用户分为两类"
        
        logger.info(f"测试问题: {question}")
        logger.info(f"候选微服务数量: {len(candidates)}")
        
        intents = await llm_module.classify(question, candidates)
        
        logger.info(f"识别出的微服务: {intents}")
        logger.info("✓ LLM模块测试通过")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ LLM模块测试失败: {str(e)}")
        return False


async def main():
    """主函数"""
    logger.info("开始LLM模块测试\n")
    
    # 测试LLM客户端
    client_ok = await test_llm_client()
    
    # 测试LLM模块
    module_ok = await test_llm_module()
    
    # 总结
    logger.info("\n=== 测试总结 ===")
    logger.info(f"LLM客户端: {'✓ 通过' if client_ok else '✗ 失败'}")
    logger.info(f"LLM模块: {'✓ 通过' if module_ok else '✗ 失败'}")
    
    if client_ok and module_ok:
        logger.info("\n所有测试通过！")
    else:
        logger.warning("\n部分测试失败，请检查配置和网络连接。")


if __name__ == "__main__":
    asyncio.run(main())
