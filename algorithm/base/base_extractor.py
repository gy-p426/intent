"""
Base Algorithm Extractor

算法特定参数提取器基类
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from algorithm.models import AlgorithmParameters, AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class BaseAlgorithmExtractor(ABC):
    """算法特定参数提取器基类"""
    
    def __init__(self, nl2sql_client=None):
        """
        初始化提取器
        
        Args:
            nl2sql_client: NL2SQL客户端，用于获取候选表信息
        """
        self.nl2sql_client = nl2sql_client
    
    @property
    @abstractmethod
    def algorithm_type(self) -> AlgorithmType:
        """返回支持的算法类型"""
        pass
    
    @property
    @abstractmethod
    def algorithm_name(self) -> str:
        """返回算法名称，用于注册"""
        pass
    
    @abstractmethod
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建算法特定的参数提取提示词"""
        pass
    
    @abstractmethod
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应，返回算法特定的参数结构"""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证和标准化参数"""
        pass
    
    async def _get_candidate_tables_from_nl2sql(self, question: str, window_id: str = "default") -> tuple[str, Dict[str, Any]]:
        """
        从NL2SQL服务获取候选表信息和关键词
        
        Args:
            question: 用户问题
            window_id: 窗口ID
            
        Returns:
            tuple[str, Dict[str, Any]]: (格式化的候选表信息, 完整的查询结果)
        """
        if not self.nl2sql_client:
            logger.warning("NL2SQL客户端未配置，无法获取候选表信息")
            return "（无可用数据库模式信息）", {}
        
        try:
            query_db_result = await self.nl2sql_client.query_db(question, window_id)
            
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
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        通用JSON响应解析方法
        
        支持以下格式：
        1. 纯JSON: {"key": "value"}
        2. Markdown代码块: ```json\n{...}\n```
        3. 普通代码块: ```\n{...}\n```
        4. 带其他文本的响应（提取JSON部分）
        
        Args:
            response: LLM返回的响应文本
            
        Returns:
            Dict[str, Any]: 解析后的JSON对象
            
        Raises:
            ValueError: 当无法解析JSON时
        """
        import re
        
        try:
            # 清理响应文本
            response = response.strip()
            
            # 方法1: 使用正则表达式提取Markdown代码块中的内容
            if '```' in response:
                # 匹配 ```json ... ``` 或 ``` ... ```
                pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
                    logger.debug(f"从Markdown代码块中提取JSON: {json_str[:100]}...")
                else:
                    # 如果正则失败，尝试手动提取
                    logger.debug("正则匹配失败，尝试手动提取代码块")
                    if "```json" in response:
                        start = response.find("```json") + 7
                    else:
                        start = response.find("```") + 3
                    
                    # 跳过可能的换行符
                    while start < len(response) and response[start] in '\n\r ':
                        start += 1
                    
                    end = response.find("```", start)
                    if end > start:
                        json_str = response[start:end].strip()
                        logger.debug(f"手动提取JSON: {json_str[:100]}...")
                    else:
                        json_str = response
            else:
                json_str = response
            
            # 方法2: 查找JSON对象的边界
            # 尝试找到第一个 { 和最后一个 }
            start_idx = json_str.find('{')
            end_idx = json_str.rfind('}')
            
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                logger.error(f"响应中未找到有效的JSON对象")
                logger.error(f"原始响应: {response[:500]}")
                raise ValueError(f"响应中未找到有效的JSON对象")
            
            # 提取JSON部分
            json_str = json_str[start_idx:end_idx + 1]
            
            # 方法3: 解析JSON
            result = json.loads(json_str)
            logger.debug(f"JSON解析成功，包含keys: {list(result.keys())}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            logger.error(f"原始响应（前500字符）: {response[:500]}")
            logger.error(f"尝试解析的JSON字符串（前500字符）: {json_str[:500] if 'json_str' in locals() else 'N/A'}")
            raise ValueError(f"LLM响应格式错误，无法解析JSON: {str(e)}")
        except Exception as e:
            logger.error(f"响应解析失败: {str(e)}")
            logger.error(f"原始响应（前500字符）: {response[:500]}")
            raise ValueError(f"参数提取响应解析失败: {str(e)}")