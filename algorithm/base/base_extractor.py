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
        """通用JSON响应解析方法"""
        try:
            # 清理响应文本
            response = response.strip()
            
            # 处理可能的markdown代码块格式
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            
            # 尝试查找JSON对象
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                raise ValueError(f"响应中未找到有效的JSON对象: {response}")
            
            json_str = response[start_idx:end_idx + 1]
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}, 响应内容: {response}")
            raise ValueError(f"LLM响应格式错误，无法解析JSON: {str(e)}")
        except Exception as e:
            logger.error(f"响应解析失败: {str(e)}, 响应内容: {response}")
            raise ValueError(f"参数提取响应解析失败: {str(e)}")