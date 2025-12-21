"""
Database Schema Retriever

This module provides functionality to connect to MySQL database and retrieve
table schema information, specifically from the table_columns table in the nl2sql database.
It includes caching mechanisms and intelligent matching logic for algorithm parameters.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import aiomysql
from algorithm.models import DatabaseColumn
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)


class DatabaseSchemaRetriever:
    """
    数据库模式信息获取器
    
    负责连接MySQL数据库，获取table_columns表信息，
    实现缓存机制和智能匹配逻辑
    """
    
    def __init__(self):
        """初始化数据库模式获取器"""
        self.settings = get_settings()
        self._connection_pool: Optional[aiomysql.Pool] = None
        self._schema_cache: Dict[str, List[DatabaseColumn]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)  # 缓存30分钟
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """
        初始化数据库连接池
        
        Raises:
            ConnectionError: 数据库连接失败时抛出
        """
        try:
            self._connection_pool = await aiomysql.create_pool(
                host=self.settings.mysql_host,
                port=self.settings.mysql_port,
                user=self.settings.mysql_username,
                password=self.settings.mysql_password,
                db=self.settings.mysql_database,
                charset='utf8mb4',
                autocommit=True,
                minsize=1,
                maxsize=10,
                echo=False
            )
            logger.info(f"数据库连接池初始化成功: {self.settings.mysql_host}:{self.settings.mysql_port}")
        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {str(e)}")
            raise ConnectionError(f"无法连接到MySQL数据库: {str(e)}")
    
    async def close(self) -> None:
        """关闭数据库连接池"""
        if self._connection_pool:
            self._connection_pool.close()
            await self._connection_pool.wait_closed()
            logger.info("数据库连接池已关闭")
    
    async def get_database_schema(self, force_refresh: bool = False) -> List[DatabaseColumn]:
        """
        获取数据库模式信息
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            List[DatabaseColumn]: 数据库列信息列表
            
        Raises:
            ConnectionError: 数据库连接失败时抛出
            RuntimeError: 查询执行失败时抛出
        """
        async with self._lock:
            # 检查缓存是否有效
            if not force_refresh and self._is_cache_valid():
                logger.debug("使用缓存的数据库模式信息")
                return list(self._schema_cache.get('all', []))
            
            # 从数据库获取最新信息
            logger.info("从数据库获取模式信息")
            schema_columns = await self._fetch_schema_from_database()
            
            # 更新缓存
            self._schema_cache['all'] = schema_columns
            self._cache_timestamp = datetime.now()
            
            logger.info(f"获取到 {len(schema_columns)} 个数据库列信息")
            return schema_columns
    
    async def get_schema_by_tables(self, table_names: List[str]) -> List[DatabaseColumn]:
        """
        根据表名获取特定表的模式信息，仅作测试用
        
        Args:
            table_names: 表名列表
            
        Returns:
            List[DatabaseColumn]: 指定表的列信息
        """
        all_schema = await self.get_database_schema()
        table_set = set(table_names)
        
        filtered_schema = [
            column for column in all_schema 
            if column.table_name in table_set
        ]
        
        logger.debug(f"筛选出 {len(filtered_schema)} 个列信息，来自表: {table_names}")
        return filtered_schema
    
    async def search_columns_by_keywords(self, keywords: List[str]) -> List[DatabaseColumn]:
        """
        根据关键词搜索相关的数据库列，仅作测试用
        
        Args:
            keywords: 搜索关键词列表
            
        Returns:
            List[DatabaseColumn]: 匹配的列信息
        """
        all_schema = await self.get_database_schema()
        
        # 将关键词转换为小写以进行不区分大小写的匹配
        keywords_lower = [kw.lower() for kw in keywords]
        
        matched_columns = []
        for column in all_schema:
            # 检查列名和注释是否包含关键词
            column_text = f"{column.column_name} {column.column_comment}".lower()
            
            for keyword in keywords_lower:
                if keyword in column_text:
                    matched_columns.append(column)
                    break  # 找到一个匹配就足够了
        
        logger.debug(f"关键词 {keywords} 匹配到 {len(matched_columns)} 个列")
        return matched_columns
    
    def match_algorithm_parameters(
        self, 
        algorithm_params: Dict[str, any], 
        database_schema: List[DatabaseColumn]
    ) -> Dict[str, List[DatabaseColumn]]:
        """
        智能匹配算法参数与数据库列
        
        Args:
            algorithm_params: 算法参数字典
            database_schema: 数据库模式信息
            
        Returns:
            Dict[str, List[DatabaseColumn]]: 参数名到匹配列的映射
        """
        matches = {}
        
        for param_name, param_value in algorithm_params.items():
            if isinstance(param_value, str):
                # 使用参数名和值作为搜索关键词
                search_terms = [param_name, param_value]
                matched_columns = self._find_matching_columns(search_terms, database_schema)
                matches[param_name] = matched_columns
            elif isinstance(param_value, list):
                # 如果参数值是列表，使用列表中的字符串值
                search_terms = [param_name] + [str(v) for v in param_value if isinstance(v, str)]
                matched_columns = self._find_matching_columns(search_terms, database_schema)
                matches[param_name] = matched_columns
            else:
                # 其他类型只使用参数名
                matched_columns = self._find_matching_columns([param_name], database_schema)
                matches[param_name] = matched_columns
        
        logger.debug(f"算法参数匹配结果: {[(k, len(v)) for k, v in matches.items()]}")
        return matches
    
    def get_table_names(self, database_schema: List[DatabaseColumn]) -> Set[str]:
        """
        从数据库模式中提取所有表名
        
        Args:
            database_schema: 数据库模式信息
            
        Returns:
            Set[str]: 表名集合
        """
        return {column.table_name for column in database_schema}
    
    def get_columns_by_data_type(
        self, 
        database_schema: List[DatabaseColumn], 
        data_types: List[str]
    ) -> List[DatabaseColumn]:
        """
        根据数据类型筛选列
        
        Args:
            database_schema: 数据库模式信息
            data_types: 数据类型列表（如 ['int', 'varchar', 'decimal']）
            
        Returns:
            List[DatabaseColumn]: 匹配指定数据类型的列
        """
        data_types_lower = [dt.lower() for dt in data_types]
        
        matched_columns = [
            column for column in database_schema
            if any(dt in column.data_type.lower() for dt in data_types_lower)
        ]
        
        logger.debug(f"数据类型 {data_types} 匹配到 {len(matched_columns)} 个列")
        return matched_columns
    
    async def _fetch_schema_from_database(self) -> List[DatabaseColumn]:
        """
        从数据库获取table_columns表信息
        
        Returns:
            List[DatabaseColumn]: 数据库列信息列表
            
        Raises:
            ConnectionError: 数据库连接失败时抛出
            RuntimeError: 查询执行失败时抛出
        """
        if not self._connection_pool:
            await self.initialize()
        
        try:
            async with self._connection_pool.acquire() as connection:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    # 查询table_columns表获取有列注释的列信息
                    query = """
                    SELECT 
                        table_name,
                        column_name,
                        column_comment,
                        data_type,
                        is_nullable,
                        column_default
                    FROM table_columns 
                    WHERE column_comment IS NOT NULL 
                      AND column_comment != '' 
                      AND TRIM(column_comment) != ''
                    ORDER BY table_name, column_name
                    """
                    
                    await cursor.execute(query)
                    rows = await cursor.fetchall()
                    
                    # 转换为DatabaseColumn对象，只包含有注释的列
                    columns = []
                    for row in rows:
                        # 确保列注释不为空
                        if row['column_comment'] and row['column_comment'].strip():
                            column = DatabaseColumn(
                                table_name=row['table_name'],
                                column_name=row['column_name'],
                                column_comment=row['column_comment'].strip(),
                                data_type=row['data_type'],
                                is_nullable=row['is_nullable'] == 'YES' if isinstance(row['is_nullable'], str) else bool(row['is_nullable']),
                                column_default=row['column_default']
                            )
                            columns.append(column)
                    
                    return columns
                    
        except Exception as e:
            logger.error(f"从数据库获取模式信息失败: {str(e)}")
            raise RuntimeError(f"查询数据库模式信息失败: {str(e)}")
    
    def _is_cache_valid(self) -> bool:
        """
        检查缓存是否有效
        
        Returns:
            bool: 缓存是否有效
        """
        if not self._cache_timestamp or 'all' not in self._schema_cache:
            return False
        
        return datetime.now() - self._cache_timestamp < self._cache_ttl
    
    def _find_matching_columns(
        self, 
        search_terms: List[str], 
        database_schema: List[DatabaseColumn]
    ) -> List[DatabaseColumn]:
        """
        根据搜索词查找匹配的数据库列
        
        Args:
            search_terms: 搜索词列表
            database_schema: 数据库模式信息
            
        Returns:
            List[DatabaseColumn]: 匹配的列信息
        """
        if not search_terms:
            return []
        
        # 将搜索词转换为小写
        search_terms_lower = [term.lower() for term in search_terms]
        
        matched_columns = []
        for column in database_schema:
            # 构建搜索文本：列名 + 注释 + 表名
            search_text = f"{column.column_name} {column.column_comment} {column.table_name}".lower()
            
            # 检查是否有任何搜索词匹配
            for term in search_terms_lower:
                if term in search_text:
                    matched_columns.append(column)
                    break  # 找到一个匹配就足够了
        
        return matched_columns