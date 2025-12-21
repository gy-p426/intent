"""
NL2SQL Response Processor

Handles parsing, validation, and processing of NL2SQL service responses.
Provides error handling and graceful degradation for various response scenarios.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from algorithm.models import NL2SQLResponse


logger = logging.getLogger(__name__)


class NL2SQLResponseProcessor:
    """NL2SQL响应处理器"""
    
    def __init__(self):
        self.response_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_execution_time": 0.0
        }
    
    def process_response(
        self, 
        response_data: Dict[str, Any], 
        request_question: str
    ) -> NL2SQLResponse:
        """
        处理NL2SQL服务响应
        
        Args:
            response_data: 原始响应数据
            request_question: 原始请求问题（用于日志记录）
            
        Returns:
            NL2SQLResponse: 处理后的响应对象
            
        Raises:
            ValueError: 响应数据无效时抛出
        """
        self.response_stats["total_requests"] += 1
        
        try:
            # 基本字段提取和验证
            sql_statement, execution_result, execution_time_ms, error = self._extract_basic_fields(response_data)
            
            # 验证SQL语句
            if sql_statement and not error:
                self._validate_sql_statement(sql_statement)
            
            # 验证执行结果
            if execution_result:
                self._validate_execution_result(execution_result)
            
            # 处理错误情况
            if error:
                self._handle_error_response(error, request_question)
            else:
                self.response_stats["successful_requests"] += 1
            
            # 更新统计信息
            self._update_stats(execution_time_ms)
            
            # 记录处理结果
            self._log_processing_result(sql_statement, execution_result, execution_time_ms, error)
            
            return NL2SQLResponse(
                sql_statement=sql_statement,
                execution_result=execution_result,
                execution_time_ms=execution_time_ms,
                error=error
            )
            
        except Exception as e:
            self.response_stats["failed_requests"] += 1
            logger.error(f"处理NL2SQL响应失败: {str(e)}")
            raise ValueError(f"NL2SQL响应处理失败: {str(e)}")
    
    def _extract_basic_fields(self, response_data: Dict[str, Any]) -> Tuple[str, List[Dict], int, Optional[str]]:
        """
        提取响应的基本字段
        
        Args:
            response_data: 原始响应数据
            
        Returns:
            Tuple: (sql_statement, execution_result, execution_time_ms, error)
        """
        # 提取SQL语句
        sql_statement = response_data.get("sql_statement", "")
        if not isinstance(sql_statement, str):
            sql_statement = str(sql_statement) if sql_statement is not None else ""
        
        # 提取执行结果
        execution_result = response_data.get("execution_result", [])
        if not isinstance(execution_result, list):
            if execution_result is None:
                execution_result = []
            elif isinstance(execution_result, dict):
                execution_result = [execution_result]
            else:
                logger.warning(f"执行结果类型异常: {type(execution_result)}")
                # 尝试将其他类型转换为列表
                try:
                    execution_result = [execution_result]
                except Exception:
                    execution_result = []
        
        # 提取执行时间
        execution_time_ms = response_data.get("execution_time_ms", 0)
        if not isinstance(execution_time_ms, (int, float)):
            try:
                execution_time_ms = float(execution_time_ms) if execution_time_ms is not None else 0
            except (ValueError, TypeError):
                logger.warning(f"执行时间格式异常: {execution_time_ms}")
                execution_time_ms = 0
        
        # 提取错误信息
        error = response_data.get("error")
        if error and not isinstance(error, str):
            error = str(error)
        
        return sql_statement, execution_result, int(execution_time_ms), error
    
    def _validate_sql_statement(self, sql_statement: str) -> None:
        """
        验证SQL语句的基本格式
        
        Args:
            sql_statement: SQL语句
            
        Raises:
            ValueError: SQL语句格式无效时抛出
        """
        if not sql_statement.strip():
            logger.warning("收到空的SQL语句")
            return
        
        # 基本SQL关键词检查
        sql_upper = sql_statement.upper().strip()
        valid_sql_starts = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH', 'SHOW', 'DESCRIBE', 'EXPLAIN']
        
        if not any(sql_upper.startswith(keyword) for keyword in valid_sql_starts):
            logger.warning(f"SQL语句可能格式异常: {sql_statement[:50]}...")
        
        # 检查SQL长度
        if len(sql_statement) > 10000:
            logger.warning(f"SQL语句过长: {len(sql_statement)} 字符")
    
    def _validate_execution_result(self, execution_result: List[Dict]) -> None:
        """
        验证执行结果的格式
        
        Args:
            execution_result: 执行结果列表
        """
        if not execution_result:
            logger.debug("执行结果为空")
            return
        
        # 检查结果数量
        if len(execution_result) > 10000:
            logger.warning(f"执行结果行数过多: {len(execution_result)} 行")
        
        # 检查第一行的格式
        first_row = execution_result[0]
        if not isinstance(first_row, dict):
            logger.warning(f"执行结果第一行格式异常: {type(first_row)}")
        else:
            # 记录列信息
            columns = list(first_row.keys())
            logger.debug(f"执行结果包含 {len(columns)} 列: {columns[:10]}")
    
    def _handle_error_response(self, error: str, request_question: str) -> None:
        """
        处理错误响应
        
        Args:
            error: 错误信息
            request_question: 原始请求问题
        """
        self.response_stats["failed_requests"] += 1
        
        # 分类错误类型
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            logger.error(f"NL2SQL查询超时: {request_question[:100]}...")
        elif "syntax" in error_lower or "sql" in error_lower:
            logger.error(f"SQL语法错误: {error}")
        elif "connection" in error_lower or "network" in error_lower:
            logger.error(f"数据库连接错误: {error}")
        elif "permission" in error_lower or "access" in error_lower:
            logger.error(f"数据库权限错误: {error}")
        else:
            logger.error(f"NL2SQL未知错误: {error}")
    
    def _update_stats(self, execution_time_ms: int) -> None:
        """
        更新统计信息
        
        Args:
            execution_time_ms: 执行时间（毫秒）
        """
        if self.response_stats["total_requests"] > 0:
            # 计算平均执行时间
            current_avg = self.response_stats["avg_execution_time"]
            total_requests = self.response_stats["total_requests"]
            
            self.response_stats["avg_execution_time"] = (
                (current_avg * (total_requests - 1) + execution_time_ms) / total_requests
            )
    
    def _log_processing_result(
        self, 
        sql_statement: str, 
        execution_result: List[Dict], 
        execution_time_ms: int, 
        error: Optional[str]
    ) -> None:
        """
        记录处理结果日志
        
        Args:
            sql_statement: SQL语句
            execution_result: 执行结果
            execution_time_ms: 执行时间
            error: 错误信息
        """
        if error:
            logger.warning(f"NL2SQL响应包含错误: {error}")
        else:
            logger.info(
                f"NL2SQL响应处理成功 - "
                f"SQL长度: {len(sql_statement)}, "
                f"结果行数: {len(execution_result)}, "
                f"执行时间: {execution_time_ms}ms"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取处理统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        success_rate = 0.0
        if self.response_stats["total_requests"] > 0:
            success_rate = (
                self.response_stats["successful_requests"] / 
                self.response_stats["total_requests"] * 100
            )
        
        return {
            **self.response_stats,
            "success_rate": round(success_rate, 2),
            "avg_execution_time": round(self.response_stats["avg_execution_time"], 2)
        }
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.response_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_execution_time": 0.0
        }