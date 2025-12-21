"""
Base Algorithm Extractor

算法特定参数提取器基类
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from algorithm.models import AlgorithmParameters, AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class BaseAlgorithmExtractor(ABC):
    """算法特定参数提取器基类"""
    
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
    def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: List[DatabaseColumn]
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