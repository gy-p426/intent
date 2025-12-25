"""
NL2SQL Client Implementation

Client for interfacing with the existing NL2SQL service to generate
SQL queries and retrieve data for algorithm processing.

This client provides:
- HTTP request encapsulation with timeout and retry mechanisms
- Response data parsing and validation
- Comprehensive error handling and graceful degradation
- Structured logging for service calls
- Service discovery integration with Nacos
"""

import logging
import aiohttp
import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from algorithm.models import NL2SQLRequest, NL2SQLResponse
from algorithm.interfaces import INL2SQLClient
from algorithm.clients.nl2sql_response_processor import NL2SQLResponseProcessor
from infrastructure.config import get_settings
from infrastructure.service_discovery import get_service_discovery_client


logger = logging.getLogger(__name__)


class NL2SQLClient(INL2SQLClient):
    """NL2SQL服务客户端实现（支持服务发现）"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        """
        初始化NL2SQL客户端
        
        Args:
            base_url: NL2SQL服务基础URL（可选，优先使用服务发现）
            timeout: 请求超时时间（秒）
        """
        self.settings = get_settings()
        self.static_base_url = base_url or self.settings.nl2sql_base_url
        self.timeout = timeout or self.settings.nl2sql_timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.response_processor = NL2SQLResponseProcessor()
        
        # 服务发现客户端
        self.service_discovery = get_service_discovery_client()
        
        logger.info(f"NL2SQL客户端初始化完成，服务发现模式: {self.settings.service_discovery_mode}")
    
    async def _get_service_url(self) -> str:
        """
        获取NL2SQL服务URL
        
        Returns:
            str: 服务URL
            
        Raises:
            ConnectionError: 无法获取服务URL时抛出
        """
        try:
            # 尝试通过服务发现获取URL
            discovered_url = await self.service_discovery.discover_service(
                self.settings.nl2sql_service_name
            )
            
            if discovered_url:
                logger.debug(f"通过服务发现获取NL2SQL服务URL: {discovered_url}")
                return discovered_url
            else:
                # 降级到静态配置
                logger.warning(f"服务发现失败，使用静态配置: {self.static_base_url}")
                return self.static_base_url
                
        except Exception as e:
            logger.warning(f"服务发现异常，使用静态配置: {str(e)}")
            return self.static_base_url
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话，如果不存在则创建"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def query_db(self, question: str, window_id: str = "default") -> Dict[str, Any]:
        """
        调用NL2SQL服务的/query-db接口获取候选表信息和关键词
        
        Args:
            question: 用户自然语言查询
            window_id: 窗口ID
            
        Returns:
            Dict[str, Any]: 包含候选表和关键词的完整信息
            
        Raises:
            ConnectionError: 服务连接失败时抛出
            ValueError: 请求参数无效时抛出
        """
        start_time = datetime.utcnow()
        logger.info(f"调用NL2SQL /query-db接口: {question}...")
        
        try:
            # 验证请求参数
            if not question or not question.strip():
                raise ValueError("查询问题不能为空")
            
            # 准备请求数据
            request_data = {
                "question": question,
                "windowId": window_id
            }
            
            # 获取服务URL并发送HTTP请求
            base_url = await self._get_service_url()
            session = await self._get_session()
            url = f"{base_url.rstrip('/')}/api/query/query-db"
            
            logger.debug(f"发送请求到: {url}")
            logger.debug(f"请求数据: {self._sanitize_log_data(request_data)}")
            
            async with session.post(url, json=request_data) as response:
                if response.status == 200:
                    try:
                        raw_response = await response.json()
                        
                        # 检查响应是否成功
                        if not raw_response.get('success', False):
                            error_msg = raw_response.get('message', '未知错误')
                            logger.error(f"NL2SQL /query-db接口返回失败响应: {error_msg}")
                            return {
                                'candidateTables': [],
                                'keywords': {},
                                'sessionId': None,
                                'selectedDatabases': []
                            }
                        
                        # 提取data字段中的完整信息
                        data = raw_response.get('data', {})
                        result = {
                            'candidateTables': data.get('candidateTables', []),
                            'keywords': data.get('keywords', {}),
                            'sessionId': data.get('sessionId'),
                            'selectedDatabases': data.get('selectedDatabases', [])
                        }
                        
                        # 记录成功日志
                        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                        logger.info(f"NL2SQL /query-db接口调用成功，获取到 {len(result['candidateTables'])} 个候选表，耗时: {execution_time:.2f}ms")
                        
                        return result
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"NL2SQL /query-db接口返回无效JSON: {str(e)}")
                        raise ConnectionError("NL2SQL /query-db接口返回无效响应格式")
                else:
                    error_text = await response.text()
                    logger.error(f"NL2SQL /query-db接口返回错误: {response.status} - {error_text}")
                    raise ConnectionError(f"NL2SQL /query-db接口错误: HTTP {response.status}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"NL2SQL /query-db接口连接失败: {str(e)}")
            raise ConnectionError(f"无法连接到NL2SQL /query-db接口: {str(e)}")
        except asyncio.TimeoutError:
            logger.error("NL2SQL /query-db接口请求超时")
            raise ConnectionError("NL2SQL /query-db接口请求超时")
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"NL2SQL /query-db接口调用失败，耗时: {execution_time:.2f}ms，错误: {str(e)}")
            raise

    async def query_sql(
        self, 
        question: str, 
        candidate_tables: List[str], 
        merged_keywords: Dict[str, Any], 
        window_id: str, 
        session_id: str
    ) -> NL2SQLResponse:
        """
        调用NL2SQL服务的/query-sql接口生成和执行SQL
        
        Args:
            question: 用户自然语言查询
            candidate_tables: 候选表信息列表
            merged_keywords: 合并的关键词
            window_id: 窗口ID
            session_id: 会话ID
            
        Returns:
            NL2SQLResponse: NL2SQL响应
            
        Raises:
            ConnectionError: 服务连接失败时抛出
            ValueError: 请求参数无效时抛出
        """
        start_time = datetime.utcnow()
        logger.info(f"调用NL2SQL /query-sql接口: {question}...")
        
        try:
            # 验证请求参数
            if not question or not question.strip():
                raise ValueError("查询问题不能为空")
            
            if not candidate_tables:
                logger.warning("候选表列表为空，可能影响SQL生成质量")
            
            # 准备请求数据
            request_data = {
                "question": question,
                "candidateTables": candidate_tables,
                "mergedKeywords": merged_keywords,
                "windowId": window_id,
                "sessionId": session_id
            }
            
            # 获取服务URL并发送HTTP请求
            base_url = await self._get_service_url()
            session = await self._get_session()
            url = f"{base_url.rstrip('/')}/api/query/query-sql"
            
            logger.debug(f"发送请求到: {url}")
            logger.debug(f"请求数据: {self._sanitize_log_data(request_data)}")
            
            async with session.post(url, json=request_data) as response:
                response_data = await self._handle_response(response)
                
                # 使用响应处理器处理响应数据
                nl2sql_response = self.response_processor.process_response(response_data, question)
                
                # 记录成功日志
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info(f"NL2SQL /query-sql接口调用成功，耗时: {execution_time:.2f}ms")
                logger.debug(f"NL2SQL /query-sql接口返回数据: {self._sanitize_log_data(response_data)}")
                
                return nl2sql_response
                    
        except aiohttp.ClientError as e:
            logger.error(f"NL2SQL /query-sql接口连接失败: {str(e)}")
            raise ConnectionError(f"无法连接到NL2SQL /query-sql接口: {str(e)}")
        except asyncio.TimeoutError:
            logger.error("NL2SQL /query-sql接口请求超时")
            raise ConnectionError("NL2SQL /query-sql接口请求超时")
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"NL2SQL /query-sql接口调用失败，耗时: {execution_time:.2f}ms，错误: {str(e)}")
            raise

    async def query(self, request: NL2SQLRequest) -> NL2SQLResponse:
        """
        调用NL2SQL服务（兼容旧接口，内部使用新的两阶段接口）
        
        Args:
            request: NL2SQL请求
            
        Returns:
            NL2SQLResponse: NL2SQL响应
            
        Raises:
            ConnectionError: 服务连接失败时抛出
            ValueError: 请求参数无效时抛出
        """
        start_time = datetime.utcnow()
        logger.info(f"调用NL2SQL服务（两阶段模式）: {request.question}...")
        
        try:
            # 验证请求参数
            self._validate_request(request)
            
            # 第一阶段：获取候选表和关键词
            logger.debug("执行第一阶段：获取候选表和关键词")
            query_db_result = await self.query_db(request.question, request.window_id)
            
            # 第二阶段：生成和执行SQL
            logger.debug("执行第二阶段：生成和执行SQL")
            nl2sql_response = await self.query_sql(
                question=request.question,
                candidate_tables=query_db_result['candidateTables'],
                merged_keywords=query_db_result['keywords'],
                window_id=request.window_id,
                session_id=request.session_id
            )
            
            # 记录总体成功日志
            total_execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"NL2SQL服务（两阶段模式）调用成功，总耗时: {total_execution_time:.2f}ms")
            
            return nl2sql_response
                    
        except Exception as e:
            total_execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"NL2SQL服务（两阶段模式）调用失败，总耗时: {total_execution_time:.2f}ms，错误: {str(e)}")
            raise

    async def query_with_candidates(
        self, 
        question: str, 
        candidate_tables: List[str], 
        keywords: Dict[str, Any], 
        window_id: str, 
        session_id: str
    ) -> NL2SQLResponse:
        """
        使用预先获取的候选表和关键词调用NL2SQL服务，避免重复调用query-db
        
        Args:
            question: 用户自然语言查询
            candidate_tables: 预先获取的候选表信息列表
            keywords: 预先获取的关键词信息
            window_id: 窗口ID
            session_id: 会话ID
            
        Returns:
            NL2SQLResponse: NL2SQL响应
            
        Raises:
            ConnectionError: 服务连接失败时抛出
            ValueError: 请求参数无效时抛出
        """
        start_time = datetime.utcnow()
        logger.info(f"调用NL2SQL服务（使用预先获取的候选表）: {question}...")
        
        try:
            # 验证请求参数
            if not question or not question.strip():
                raise ValueError("查询问题不能为空")
            
            if not candidate_tables:
                logger.warning("候选表列表为空，可能影响SQL生成质量")
            
            # 直接调用query_sql，跳过query_db阶段
            logger.debug(f"使用 {len(candidate_tables)} 个预先获取的候选表调用query-sql接口")
            nl2sql_response = await self.query_sql(
                question=question,
                candidate_tables=candidate_tables,
                merged_keywords=keywords,
                window_id=window_id,
                session_id=session_id
            )
            
            # 记录总体成功日志
            total_execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"NL2SQL服务（使用预先候选表）调用成功，总耗时: {total_execution_time:.2f}ms")
            
            return nl2sql_response
                    
        except Exception as e:
            total_execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"NL2SQL服务（使用预先候选表）调用失败，总耗时: {total_execution_time:.2f}ms，错误: {str(e)}")
            raise
    
    async def query_with_retry(
        self, 
        request: NL2SQLRequest, 
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> NL2SQLResponse:
        """
        带重试机制的NL2SQL查询
        
        Args:
            request: NL2SQL请求
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            
        Returns:
            NL2SQLResponse: NL2SQL响应
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self.query(request)
            except ConnectionError as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(f"NL2SQL查询失败，{retry_delay}秒后重试 (尝试 {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"NL2SQL查询重试{max_retries}次后仍然失败")
            except Exception as e:
                # 对于非连接错误，不进行重试
                logger.error(f"NL2SQL查询失败（不重试）: {str(e)}")
                raise
        
        # 所有重试都失败了
        raise last_exception
    
    async def health_check(self) -> bool:
        """
        检查NL2SQL服务健康状态
        
        Returns:
            bool: 服务是否健康
        """
        try:
            base_url = await self._get_service_url()
            session = await self._get_session()
            url = f"{base_url.rstrip('/')}/health"
            
            async with session.get(url) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"NL2SQL服务健康检查失败: {str(e)}")
            return False
    
    async def close(self):
        """关闭客户端连接"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("NL2SQL客户端连接已关闭")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    def _validate_request(self, request: NL2SQLRequest) -> None:
        """
        验证请求参数
        
        Args:
            request: NL2SQL请求
            
        Raises:
            ValueError: 请求参数无效时抛出
        """
        if not request.question or not request.question.strip():
            raise ValueError("查询问题不能为空")
        
        if len(request.question) > 1000:
            raise ValueError("查询问题长度不能超过1000个字符")
        
        if not request.session_id or not request.session_id.strip():
            raise ValueError("会话ID不能为空")
        
        if not request.window_id or not request.window_id.strip():
            raise ValueError("窗口ID不能为空")
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """
        处理HTTP响应
        
        Args:
            response: HTTP响应对象
            
        Returns:
            Dict[str, Any]: 响应数据
            
        Raises:
            ConnectionError: 响应状态码非200时抛出
        """
        if response.status == 200:
            try:
                raw_response = await response.json()
                
                # 检查响应是否成功
                if not raw_response.get('success', False):
                    error_msg = raw_response.get('message', '未知错误')
                    logger.error(f"NL2SQL服务返回失败响应: {error_msg}")
                    return {
                        'sql_statement': '',
                        'execution_result': [],
                        'execution_time_ms': 0,
                        'error': error_msg
                    }
                
                # 提取data字段中的实际数据
                data = raw_response.get('data', {})
                
                # 转换为响应处理器期望的格式
                return {
                    'sql_statement': data.get('sql', ''),
                    'execution_result': data.get('results', []),
                    'execution_time_ms': data.get('executionTime', 0),
                    'error': None
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"NL2SQL服务返回无效JSON: {str(e)}")
                raise ConnectionError("NL2SQL服务返回无效响应格式")
        elif response.status == 400:
            error_text = await response.text()
            logger.error(f"NL2SQL服务请求参数错误: {error_text}")
            raise ValueError(f"请求参数错误: {error_text}")
        elif response.status == 404:
            logger.error("NL2SQL服务端点不存在")
            raise ConnectionError("NL2SQL服务端点不存在")
        elif response.status == 500:
            error_text = await response.text()
            logger.error(f"NL2SQL服务内部错误: {error_text}")
            raise ConnectionError(f"NL2SQL服务内部错误: {error_text}")
        elif response.status == 503:
            logger.error("NL2SQL服务暂时不可用")
            raise ConnectionError("NL2SQL服务暂时不可用，请稍后重试")
        else:
            error_text = await response.text()
            logger.error(f"NL2SQL服务返回未知错误: {response.status} - {error_text}")
            raise ConnectionError(f"NL2SQL服务错误: HTTP {response.status}")
    
    def _parse_response(self, response_data: Dict[str, Any]) -> NL2SQLResponse:
        """
        解析和验证响应数据
        
        Args:
            response_data: 原始响应数据
            
        Returns:
            NL2SQLResponse: 解析后的响应对象
            
        Raises:
            ValueError: 响应数据格式无效时抛出
        """
        try:
            # 提取基本字段
            sql_statement = response_data.get("sql_statement", "")
            execution_result = response_data.get("execution_result", [])
            execution_time_ms = response_data.get("execution_time_ms", 0)
            error = response_data.get("error")
            
            # 验证数据类型
            if not isinstance(sql_statement, str):
                logger.warning("SQL语句不是字符串类型，尝试转换")
                sql_statement = str(sql_statement) if sql_statement is not None else ""
            
            if not isinstance(execution_result, list):
                logger.warning("执行结果不是列表类型，尝试转换")
                execution_result = [] if execution_result is None else [execution_result]
            
            if not isinstance(execution_time_ms, (int, float)):
                logger.warning("执行时间不是数字类型，设置为0")
                execution_time_ms = 0
            
            # 记录响应统计信息
            logger.debug(f"解析NL2SQL响应: SQL长度={len(sql_statement)}, "
                        f"结果行数={len(execution_result)}, "
                        f"执行时间={execution_time_ms}ms, "
                        f"有错误={'是' if error else '否'}")
            
            return NL2SQLResponse(
                sql_statement=sql_statement,
                execution_result=execution_result,
                execution_time_ms=int(execution_time_ms),
                error=error
            )
            
        except Exception as e:
            logger.error(f"解析NL2SQL响应失败: {str(e)}")
            logger.debug(f"原始响应数据: {response_data}")
            raise ValueError(f"NL2SQL响应数据格式无效: {str(e)}")
    
    def _sanitize_log_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理日志数据，避免记录敏感信息
        
        Args:
            data: 原始数据
            
        Returns:
            Dict[str, Any]: 清理后的数据
        """
        sanitized = data.copy()
        
        # 截断长问题以避免日志过长
        if "question" in sanitized and len(sanitized["question"]) > 200:
            sanitized["question"] = sanitized["question"][:200] + "..."
        
        return sanitized
    
    async def batch_query(
        self, 
        requests: List[NL2SQLRequest], 
        max_concurrent: int = 5
    ) -> List[NL2SQLResponse]:
        """
        批量查询NL2SQL服务
        
        Args:
            requests: NL2SQL请求列表
            max_concurrent: 最大并发数
            
        Returns:
            List[NL2SQLResponse]: 响应列表
        """
        logger.info(f"开始批量查询，共 {len(requests)} 个请求，最大并发数: {max_concurrent}")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _query_with_semaphore(request: NL2SQLRequest) -> NL2SQLResponse:
            async with semaphore:
                return await self.query_with_retry(request)
        
        try:
            responses = await asyncio.gather(
                *[_query_with_semaphore(req) for req in requests],
                return_exceptions=True
            )
            
            # 处理异常结果
            processed_responses = []
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    logger.error(f"批量查询第 {i+1} 个请求失败: {str(response)}")
                    # 创建错误响应
                    processed_responses.append(NL2SQLResponse(
                        sql_statement="",
                        execution_result=[],
                        execution_time_ms=0,
                        error=str(response)
                    ))
                else:
                    processed_responses.append(response)
            
            logger.info(f"批量查询完成，成功: {sum(1 for r in processed_responses if not r.error)} 个")
            return processed_responses
            
        except Exception as e:
            logger.error(f"批量查询失败: {str(e)}")
            raise
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        获取服务统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "service_name": self.settings.nl2sql_service_name,
            "static_url": self.static_base_url,
            "timeout": self.timeout,
            "discovery_mode": self.settings.service_discovery_mode,
            "discovery_enabled": self.settings.service_discovery_enabled,
            "response_stats": self.response_processor.get_stats()
        }
    
    async def validate_service_connection(self) -> Dict[str, Any]:
        """
        验证服务连接状态
        
        Returns:
            Dict[str, Any]: 连接状态信息
        """
        start_time = datetime.utcnow()
        
        try:
            # 获取当前使用的服务URL
            current_url = await self._get_service_url()
            
            # 尝试健康检查
            is_healthy = await self.health_check()
            
            if is_healthy:
                # 尝试简单查询测试
                test_request = NL2SQLRequest(
                    question="测试连接",
                    window_id="test",
                    session_id="connection_test"
                )
                
                try:
                    await self.query(test_request)
                    connection_status = "healthy"
                    error_message = None
                except Exception as e:
                    connection_status = "degraded"
                    error_message = f"查询测试失败: {str(e)}"
            else:
                connection_status = "unhealthy"
                error_message = "健康检查失败"
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return {
                "status": connection_status,
                "response_time_ms": round(response_time, 2),
                "error": error_message,
                "timestamp": start_time.isoformat(),
                "current_url": current_url,
                "service_name": self.settings.nl2sql_service_name,
                "discovery_mode": self.settings.service_discovery_mode
            }
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"服务连接验证失败: {str(e)}")
            
            return {
                "status": "error",
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "timestamp": start_time.isoformat(),
                "current_url": self.static_base_url,
                "service_name": self.settings.nl2sql_service_name,
                "discovery_mode": self.settings.service_discovery_mode
            }