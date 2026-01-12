"""
Algorithm Integration Service Interfaces

Defines abstract base classes and interfaces for all algorithm integration components.
This ensures consistent implementation across different components and enables easy testing.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncGenerator
from algorithm.models import (
    AlgorithmType, AlgorithmParameters, AlgorithmConfig,
    NL2SQLRequest, NL2SQLResponse, AlgorithmExecutionRequest,
    AlgorithmExecutionResponse, AsyncTaskResponse, AlgorithmResponse,
    DatabaseColumn, AlgorithmResponseGenerator
)


class IAlgorithmRouter(ABC):
    """算法路由器接口"""
    
    @abstractmethod
    async def route_to_algorithm(self, question: str) -> AlgorithmType:
        """
        将用户问题路由到算法类型
        
        Args:
            question: 用户自然语言查询
            
        Returns:
            AlgorithmType: 识别的算法类型
            
        Raises:
            ValueError: 无法识别算法类型时抛出
        """
        pass


class IParameterExtractor(ABC):
    """参数提取器接口"""
    
    @abstractmethod
    async def extract_parameters(
        self, 
        question: str, 
        algorithm_type: AlgorithmType,
        database_schema: List[DatabaseColumn],
        window_id: str = "default"
    ) -> AlgorithmParameters:
        """
        从用户查询中提取算法参数
        
        Args:
            question: 用户自然语言查询
            algorithm_type: 算法类型
            database_schema: 数据库模式信息
            window_id: 窗口ID
            
        Returns:
            AlgorithmParameters: 提取的算法参数
            
        Raises:
            ValueError: 参数提取失败时抛出
        """
        pass

    @abstractmethod
    async def generate_normalized_query_from_manual_selection(
        self,
        *,
        original_question: str,
        algorithm_type: AlgorithmType,
        manual_parameter_mapping: Dict[str, Any],
        user_feedback: Optional[str] = None,
    ) -> str:
        """手动流程：根据用户选择生成新的 normalized_query"""
        pass


class INL2SQLClient(ABC):
    """NL2SQL客户端接口"""
    
    @abstractmethod
    async def query(self, request: NL2SQLRequest) -> NL2SQLResponse:
        """
        调用NL2SQL服务
        
        Args:
            request: NL2SQL请求
            
        Returns:
            NL2SQLResponse: NL2SQL响应
            
        Raises:
            ConnectionError: 服务连接失败时抛出
            ValueError: 请求参数无效时抛出
        """
        pass
    
    @abstractmethod
    async def close(self):
        """关闭客户端连接"""
        pass


class IAlgorithmExecutor(ABC):
    """算法执行器接口"""
    
    @abstractmethod
    async def execute_clustering(
        self, 
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行聚类算法
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        pass
    
    @abstractmethod
    async def execute_classification(
        self, 
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行分类算法
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应(可能包含task_id)
        """
        pass
    
    @abstractmethod
    async def poll_async_task(self, task_id: str) -> AsyncGenerator[AsyncTaskResponse, None]:
        """
        轮询异步任务状态
        
        Args:
            task_id: 任务ID
            
        Yields:
            AsyncTaskResponse: 任务状态更新
        """
        pass


class ITaskManager(ABC):
    """任务管理器接口"""
    
    @abstractmethod
    async def create_task(self, task_id: str, algorithm_type: AlgorithmType) -> None:
        """
        创建任务记录
        
        Args:
            task_id: 任务ID
            algorithm_type: 算法类型
        """
        pass
    
    @abstractmethod
    async def update_task_status(self, task_id: str, status: str, result: Optional[Dict] = None) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            result: 任务结果(可选)
        """
        pass
    
    @abstractmethod
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict]: 任务状态信息
        """
        pass
    
    @abstractmethod
    async def start_task_polling(
        self, 
        task_id: str, 
        poll_function, 
        timeout_seconds: Optional[int] = None
    ) -> AsyncGenerator[AsyncTaskResponse, None]:
        """
        开始任务轮询
        
        Args:
            task_id: 任务ID
            poll_function: 轮询函数
            timeout_seconds: 超时时间（秒）
            
        Yields:
            AsyncTaskResponse: 任务状态更新
        """
        pass
    
    @abstractmethod
    async def handle_task_timeout(self, task_id: str) -> None:
        """
        处理任务超时
        
        Args:
            task_id: 任务ID
        """
        pass
    
    @abstractmethod
    async def handle_task_failure(self, task_id: str, error_message: str) -> None:
        """
        处理任务失败
        
        Args:
            task_id: 任务ID
            error_message: 错误消息
        """
        pass
    
    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否取消成功
        """
        pass


class IStreamingResponseHandler(ABC):
    """流式响应处理器接口"""
    
    @abstractmethod
    async def create_streaming_response(
        self, 
        generator: AlgorithmResponseGenerator
    ) -> Any:  # FastAPI StreamingResponse
        """
        创建流式HTTP响应
        
        Args:
            generator: 算法响应生成器
            
        Returns:
            StreamingResponse: FastAPI流式响应对象
        """
        pass
    
    @abstractmethod
    def format_stream_chunk(self, data: AlgorithmResponse) -> str:
        """
        格式化流式数据块
        
        Args:
            data: 算法响应数据
            
        Returns:
            str: 格式化的数据块
        """
        pass


class IAlgorithmConfigManager(ABC):
    """算法配置管理器接口"""
    
    @abstractmethod
    async def load_config(self) -> Dict[str, AlgorithmConfig]:
        """
        加载算法配置
        
        Returns:
            Dict[str, AlgorithmConfig]: 算法配置字典
        """
        pass
    
    @abstractmethod
    async def reload_config(self) -> None:
        """重新加载配置"""
        pass
    
    @abstractmethod
    def get_algorithm_config(self, algorithm_type: AlgorithmType) -> Optional[AlgorithmConfig]:
        """
        获取指定算法的配置
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            Optional[AlgorithmConfig]: 算法配置
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        """
        验证配置格式
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否有效
        """
        pass


class IDataProcessor(ABC):
    """数据处理器接口"""
    
    @abstractmethod
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """
        将SQL结果转换为算法输入格式
        
        Args:
            sql_result: SQL查询结果
            algorithm_config: 算法配置
            parameters: 算法参数
            
        Returns:
            AlgorithmExecutionRequest: 算法执行请求
        """
        pass
    
    @abstractmethod
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """
        验证算法输入数据
        
        Args:
            request: 算法执行请求
            algorithm_config: 算法配置
            
        Returns:
            bool: 数据是否有效
        """
        pass


class IAlgorithmIntegrationService(ABC):
    """算法集成服务主接口"""
    
    @abstractmethod
    async def process_algorithm_request(
        self, 
        question: str, 
        window_id: str, 
        session_id: str
    ) -> AlgorithmResponseGenerator:
        """
        处理算法请求的主要方法
        
        Args:
            question: 用户自然语言查询
            window_id: 窗口ID
            session_id: 会话ID
            
        Yields:
            AlgorithmResponse: 流式响应数据
        """
        pass
    
    @abstractmethod
    async def identify_algorithm_type(self, question: str) -> AlgorithmType:
        """
        识别算法类型
        
        Args:
            question: 用户查询
            
        Returns:
            AlgorithmType: 识别的算法类型
        """
        pass
    
    @abstractmethod
    async def extract_parameters(
        self, 
        question: str, 
        algorithm_type: AlgorithmType
    ) -> AlgorithmParameters:
        """
        提取算法参数
        
        Args:
            question: 用户查询
            algorithm_type: 算法类型
            
        Returns:
            AlgorithmParameters: 提取的参数
        """
        pass