"""
Agent算法分析 - 问题标准化模块

负责将用户的自然语言问题转换为更清晰、更适合SQL查询的标准化问题。
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


async def normalize_question_for_agent(
    question: str,
    window_id: str = "default",
    candidate_tables_info: Optional[str] = None
) -> str:
    """
    为Agent算法分析标准化用户问题
    
    通过大模型将用户的自然语言问题转换为更清晰、更适合SQL查询的标准化问题。
    结合数据库候选表信息，生成更准确的查询描述。
    
    Args:
        question: 用户原始问题
        window_id: 窗口ID
        candidate_tables_info: 候选表信息（格式化后的字符串）
        
    Returns:
        str: 标准化后的问题
        
    Examples:
        >>> await normalize_question_for_agent("帮我看看最近销售情况怎么样")
        "查询最近一段时间的销售数据，包括销售额、订单量等指标"
        
        >>> await normalize_question_for_agent("分析一下哪些客户比较活跃")
        "分析客户活跃度，获取客户的访问频次、购买次数等行为数据"
    """
    try:
        # 构建数据库信息部分
        db_info_section = ""
        if candidate_tables_info:
            db_info_section = f"""

数据库可用列信息：
{candidate_tables_info}

请根据数据库中的实际列信息来标准化问题，确保：
1. 使用数据库中实际存在的列注释
2. 明确指出需要查询哪些列
3. 保留用户问题中的筛选条件和时间范围"""
        
        # 构建标准化问题的提示词
        system_content = f"""你是一个数据分析助手，负责将用户的自然语言问题转换为更清晰、更适合数据查询的标准化问题。
{db_info_section}

你的任务：
1. 理解用户问题的核心意图
2. 识别关键的数据需求和分析目标
3. 将问题转换为清晰、具体的查询描述
4. 保留所有重要的业务术语和条件
5. 明确说明需要返回哪些数据列

转换原则：
- 保持问题的核心意图不变
- 使用更规范的表达方式
- 明确数据范围和筛选条件
- 去除口语化和模糊的表达
- 保留所有业务相关的关键词
- 明确列出需要查询的数据列（使用列注释）
- 说明返回几列数据

示例：
用户问题: "帮我看看最近销售情况怎么样"
标准化问题: "查询最近一段时间的销售数据，包括销售日期、销售额、订单量，返回销售日期、销售额、订单量共3列数据"

用户问题: "分析一下哪些客户比较活跃"
标准化问题: "分析客户活跃度，获取客户ID、访问频次、购买次数等行为数据，返回客户ID、访问频次、购买次数共3列数据"

用户问题: "给我看下上个月的订单"
标准化问题: "查询上个月的订单数据，包括订单号、订单金额、订单时间，返回订单号、订单金额、订单时间共3列数据"

请只返回标准化后的问题，不要添加任何解释。"""

        messages = [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": f"请将以下用户问题转换为标准化的查询问题：\n\n{question}"
            }
        ]
        
        # 调用LLM
        from llm.llm_client import LLMClient
        llm_client = LLMClient()
        response = await llm_client.chat_completion(messages)
        
        # 提取标准化问题
        normalized_question = response.strip()
        
        # 如果标准化失败或返回空，使用原始问题
        if not normalized_question or len(normalized_question) < 5:
            logger.warning(f"问题标准化返回结果过短，使用原始问题: {question}")
            return question
        
        logger.info(f"问题标准化成功: {question[:50]}... -> {normalized_question[:50]}...")
        return normalized_question
        
    except Exception as e:
        logger.warning(f"问题标准化失败，使用原始问题: {str(e)}")
        return question


async def get_candidate_tables_from_nl2sql(
    question: str,
    window_id: str,
    nl2sql_client
) -> tuple[str, Dict[str, Any]]:
    """
    从NL2SQL服务获取候选表信息
    
    Args:
        question: 用户问题
        window_id: 窗口ID
        nl2sql_client: NL2SQL客户端实例
        
    Returns:
        tuple[str, Dict[str, Any]]: (格式化的候选表信息, 完整的查询结果)
    """
    if not nl2sql_client:
        logger.warning("NL2SQL客户端未配置，无法获取候选表信息")
        return "（无可用数据库模式信息）", {}
    
    try:
        query_db_result = await nl2sql_client.query_db(question, window_id)
        
        candidate_tables = query_db_result.get('candidateTables', [])
        if not candidate_tables:
            return "（未找到相关的数据库表信息）", query_db_result
        
        # 格式化候选表信息
        formatted_tables = []
        for table_info in candidate_tables:
            # 候选表信息格式: "表名||表注释||PK:主键||FK:外键||||列名||列注释||数据类型||..."
            formatted_tables.append(f"候选表: {table_info}")
        
        formatted_schema = "\n".join(formatted_tables)
        return formatted_schema, query_db_result
        
    except Exception as e:
        logger.error(f"获取候选表信息失败: {str(e)}")
        return f"（获取数据库信息失败: {str(e)}）", {}
