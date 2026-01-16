"""
用户收藏服务

负责处理用户收藏的创建、查询、执行等功能
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from llm.llm_client import LLMClient
from services.where_template_engine import WhereTemplateEngine
from infrastructure.config import get_settings

logger = logging.getLogger(__name__)


class FavoriteService:
    """用户收藏服务"""
    
    def __init__(self, db_connection=None):
        """
        初始化收藏服务
        
        Args:
            db_connection: 数据库连接（如果为None，会自动创建）
        """
        self.db = db_connection or self._get_db_connection()
        self.where_engine = WhereTemplateEngine()
        self.llm_client = LLMClient()
        self.settings = get_settings()
    
    def _get_db_connection(self):
        """获取数据库连接"""
        import pymysql
        from infrastructure.config import get_settings
        
        settings = get_settings()
        return pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_username,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    
    def create_favorite(self, user_id: int, favorite_data: Dict[str, Any]) -> int:
        """
        创建收藏
        
        Args:
            user_id: 用户ID
            favorite_data: 收藏数据
                - favorite_name: 收藏名称
                - original_question: 原始问题
                - algorithm_type: 算法类型
                - algorithm_params: 算法参数
                - original_sql: 原始SQL
                - tags: 标签
                - description: 描述
        
        Returns:
            favorite_id: 创建的收藏ID
        """
        logger.info(f"开始创建收藏，用户ID: {user_id}, 收藏名称: {favorite_data.get('favorite_name')}")
        
        # 1. 使用LLM分析SQL，提取WHERE条件和生成options查询SQL
        llm_result = self._extract_where_with_llm(favorite_data['original_sql'])
        
        # 2. 如果LLM失败，使用Fallback方案（正则表达式）
        if not llm_result:
            logger.warning("LLM提取失败，使用Fallback方案")
            llm_result = self._extract_where_with_regex(favorite_data['original_sql'])
        
        # 3. 存储到数据库
        try:
            with self.db.cursor() as cursor:
                sql = """
                    INSERT INTO user_favorites (
                        user_id, favorite_name, original_question, algorithm_type,
                        window_id, session_id, algorithm_params, original_sql,
                        where_template, where_params, options_query_sqls,
                        tags, description
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    user_id,
                    favorite_data['favorite_name'],
                    favorite_data['original_question'],
                    favorite_data['algorithm_type'],
                    favorite_data.get('window_id'),
                    favorite_data.get('session_id'),
                    json.dumps(favorite_data['algorithm_params'], ensure_ascii=False),
                    favorite_data['original_sql'],
                    llm_result['where_template'],
                    json.dumps(llm_result['where_params'], ensure_ascii=False),
                    json.dumps(llm_result['options_query_sqls'], ensure_ascii=False),
                    favorite_data.get('tags'),
                    favorite_data.get('description')
                ))
                self.db.commit()
                favorite_id = cursor.lastrowid
                
            logger.info(f"收藏创建成功，ID: {favorite_id}")
            return favorite_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建收藏失败: {str(e)}", exc_info=True)
            raise
    
    def _extract_where_with_llm(self, original_sql: str) -> Optional[Dict[str, Any]]:
        """
        使用LLM提取WHERE条件并生成options查询SQL
        
        Args:
            original_sql: 原始SQL
        
        Returns:
            result: {
                "where_template": "...",
                "where_params": {...},
                "options_query_sqls": {...}
            }
        """
        prompt = f"""
你是一个SQL分析专家。请分析以下SQL语句，提取WHERE条件并生成查询参数选项的SQL。

原始SQL：
{original_sql}

请返回JSON格式：
{{
  "where_template": "date BETWEEN '{{start_date}}' AND '{{end_date}}' AND department = '{{department}}'",
  "where_params": {{
    "start_date": {{"value": "2024-01-01", "type": "date", "label": "开始日期"}},
    "end_date": {{"value": "2024-12-31", "type": "date", "label": "结束日期"}},
    "department": {{"value": "技术部", "type": "string", "label": "部门"}}
  }},
  "options_query_sqls": {{
    "department": "SELECT DISTINCT department FROM table_name WHERE department IS NOT NULL ORDER BY department LIMIT 100"
  }}
}}

注意：
1. 日期类型不需要生成options_query_sql
2. 字符串类型需要生成查询唯一值的SQL
3. SQL要加LIMIT 100限制
4. 只为WHERE条件中的参数生成查询SQL
5. 必须返回有效的JSON格式
"""
        
        try:
            # 调用LLM
            response = self.llm_client.chat(prompt)
            
            # 解析JSON
            # 尝试提取JSON（可能被包裹在```json```中）
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            
            result = json.loads(response)
            
            # 验证结果
            if self._validate_llm_result(result):
                logger.info("LLM成功提取WHERE条件")
                return result
            else:
                logger.warning("LLM返回结果验证失败")
                return None
            
        except Exception as e:
            logger.error(f"LLM提取WHERE条件失败: {str(e)}")
            return None
    
    def _extract_where_with_regex(self, original_sql: str) -> Dict[str, Any]:
        """
        使用正则表达式提取WHERE条件（Fallback方案）
        
        Args:
            original_sql: 原始SQL
        
        Returns:
            result: 同LLM返回格式
        """
        logger.info("使用正则表达式Fallback方案提取WHERE条件")
        
        # 提取WHERE子句
        where_clause = self._extract_where_from_sql(original_sql)
        table_name = self._extract_table_from_sql(original_sql)
        
        # 使用WhereTemplateEngine生成模板和参数
        where_template, where_params, options_query_sqls = self.where_engine.extract_params_from_where(
            where_clause, 
            table_name
        )
        
        return {
            'where_template': where_template,
            'where_params': where_params,
            'options_query_sqls': options_query_sqls
        }
    
    def _validate_llm_result(self, result: Dict[str, Any]) -> bool:
        """验证LLM返回的结果是否有效"""
        if not result:
            return False
        
        required_keys = ['where_template', 'where_params', 'options_query_sqls']
        for key in required_keys:
            if key not in result:
                logger.warning(f"LLM结果缺少必需字段: {key}")
                return False
        
        # 验证SQL语法（简单检查）
        for param_key, sql in result['options_query_sqls'].items():
            if not sql.upper().startswith('SELECT'):
                logger.warning(f"参数 {param_key} 的查询SQL格式错误")
                return False
            if 'LIMIT' not in sql.upper():
                logger.warning(f"参数 {param_key} 的查询SQL缺少LIMIT限制")
        
        return True
    
    def _extract_where_from_sql(self, sql: str) -> str:
        """从SQL中提取WHERE子句"""
        pattern = r'WHERE\s+(.+?)(?=\s+(?:GROUP BY|ORDER BY|LIMIT|$))'
        match = re.search(pattern, sql, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_table_from_sql(self, sql: str) -> str:
        """从SQL中提取表名"""
        pattern = r'FROM\s+(\w+)'
        match = re.search(pattern, sql, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    
    def get_favorite(self, favorite_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取收藏详情
        
        Args:
            favorite_id: 收藏ID
            user_id: 用户ID
        
        Returns:
            favorite: 收藏详情
        """
        try:
            with self.db.cursor() as cursor:
                sql = """
                    SELECT * FROM user_favorites
                    WHERE id = %s AND user_id = %s AND deleted = 0
                """
                cursor.execute(sql, (favorite_id, user_id))
                result = cursor.fetchone()
                
                if result:
                    # 解析JSON字段
                    result['algorithm_params'] = json.loads(result['algorithm_params'])
                    result['where_params'] = json.loads(result['where_params'])
                    result['options_query_sqls'] = json.loads(result['options_query_sqls'])
                    if result['last_where_params']:
                        result['last_where_params'] = json.loads(result['last_where_params'])
                
                return result
                
        except Exception as e:
            logger.error(f"获取收藏失败: {str(e)}", exc_info=True)
            raise
    
    def get_favorites_list(self, user_id: int, algorithm_type: Optional[str] = None,
                          page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        获取收藏列表
        
        Args:
            user_id: 用户ID
            algorithm_type: 算法类型（可选）
            page: 页码
            page_size: 每页数量
        
        Returns:
            result: {items: [], total: int, page: int, pageSize: int}
        """
        try:
            with self.db.cursor() as cursor:
                # 构建查询条件
                where_conditions = ["user_id = %s", "deleted = 0"]
                params = [user_id]
                
                if algorithm_type:
                    where_conditions.append("algorithm_type = %s")
                    params.append(algorithm_type)
                
                where_clause = " AND ".join(where_conditions)
                
                # 查询总数
                count_sql = f"SELECT COUNT(*) as total FROM user_favorites WHERE {where_clause}"
                cursor.execute(count_sql, params)
                total = cursor.fetchone()['total']
                
                # 查询列表
                offset = (page - 1) * page_size
                list_sql = f"""
                    SELECT id as favorite_id, favorite_name, algorithm_type, tags,
                           execution_count, last_executed_at, created_at
                    FROM user_favorites
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(list_sql, params + [page_size, offset])
                items = cursor.fetchall()
                
                return {
                    'items': items,
                    'total': total,
                    'page': page,
                    'pageSize': page_size
                }
                
        except Exception as e:
            logger.error(f"获取收藏列表失败: {str(e)}", exc_info=True)
            raise
    
    def update_favorite(self, favorite_id: int, user_id: int, update_data: Dict[str, Any]) -> bool:
        """
        更新收藏（仅更新名称、描述、标签）
        
        Args:
            favorite_id: 收藏ID
            user_id: 用户ID
            update_data: 更新数据
        
        Returns:
            success: 是否成功
        """
        try:
            with self.db.cursor() as cursor:
                # 构建更新字段
                update_fields = []
                params = []
                
                if 'favorite_name' in update_data:
                    update_fields.append("favorite_name = %s")
                    params.append(update_data['favorite_name'])
                
                if 'description' in update_data:
                    update_fields.append("description = %s")
                    params.append(update_data['description'])
                
                if 'tags' in update_data:
                    update_fields.append("tags = %s")
                    params.append(update_data['tags'])
                
                if not update_fields:
                    return True
                
                sql = f"""
                    UPDATE user_favorites
                    SET {', '.join(update_fields)}
                    WHERE id = %s AND user_id = %s AND deleted = 0
                """
                params.extend([favorite_id, user_id])
                
                cursor.execute(sql, params)
                self.db.commit()
                
                return cursor.rowcount > 0
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新收藏失败: {str(e)}", exc_info=True)
            raise
    
    def delete_favorites(self, favorite_ids: List[int], user_id: int) -> Dict[str, int]:
        """
        批量删除收藏（软删除）
        
        Args:
            favorite_ids: 收藏ID列表
            user_id: 用户ID
        
        Returns:
            result: {deleted_count: int, failed_count: int}
        """
        try:
            with self.db.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(favorite_ids))
                sql = f"""
                    UPDATE user_favorites
                    SET deleted = 1
                    WHERE id IN ({placeholders}) AND user_id = %s AND deleted = 0
                """
                cursor.execute(sql, favorite_ids + [user_id])
                self.db.commit()
                
                deleted_count = cursor.rowcount
                failed_count = len(favorite_ids) - deleted_count
                
                return {
                    'deleted_count': deleted_count,
                    'failed_count': failed_count
                }
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除收藏失败: {str(e)}", exc_info=True)
            raise
    
    def get_where_params_with_options(self, favorite_id: int, user_id: int) -> Dict[str, Any]:
        """
        获取WHERE参数（含实时options）
        
        Args:
            favorite_id: 收藏ID
            user_id: 用户ID
        
        Returns:
            result: {where_template, where_params (含options)}
        """
        # 1. 获取收藏
        favorite = self.get_favorite(favorite_id, user_id)
        if not favorite:
            raise ValueError(f"收藏不存在: {favorite_id}")
        
        # 2. 执行options_query_sqls获取实时options
        where_params = favorite['where_params'].copy()
        options_query_sqls = favorite['options_query_sqls']
        
        for param_key, query_sql in options_query_sqls.items():
            if param_key in where_params:
                try:
                    options = self._execute_options_query(query_sql)
                    where_params[param_key]['options'] = options
                except Exception as e:
                    logger.warning(f"查询参数 {param_key} 的options失败: {str(e)}")
                    where_params[param_key]['options'] = []
        
        return {
            'where_template': favorite['where_template'],
            'where_params': where_params
        }
    
    def _execute_options_query(self, query_sql: str) -> List[str]:
        """
        执行options查询SQL
        
        Args:
            query_sql: 查询SQL
        
        Returns:
            options: 选项列表
        """
        try:
            with self.db.cursor() as cursor:
                cursor.execute(query_sql)
                results = cursor.fetchall()
                
                # 提取第一列的值
                if results and len(results) > 0:
                    first_key = list(results[0].keys())[0]
                    return [row[first_key] for row in results if row[first_key] is not None]
                
                return []
                
        except Exception as e:
            logger.error(f"执行options查询失败: {query_sql}, {str(e)}")
            raise
    
    def __del__(self):
        """析构函数，关闭数据库连接"""
        if hasattr(self, 'db') and self.db:
            try:
                self.db.close()
            except:
                pass
    
    async def execute_favorite(self, favorite_id: int, user_id: int, 
                               use_original_params: bool = True,
                               modified_where_params: dict = None):
        """
        执行收藏
        
        Args:
            favorite_id: 收藏ID
            user_id: 用户ID
            use_original_params: 是否使用原参数
            modified_where_params: 修改的WHERE参数
        
        Returns:
            执行结果（流式生成器）
        """
        from algorithm.service import AlgorithmIntegrationService
        from algorithm.models import AlgorithmType
        
        # 1. 获取收藏
        favorite = self.get_favorite(favorite_id, user_id)
        if not favorite:
            raise ValueError(f"收藏不存在: {favorite_id}")
        
        # 2. 准备WHERE参数
        where_params = favorite['where_params'].copy()
        
        if not use_original_params and modified_where_params:
            # 合并修改的参数
            for key, value in modified_where_params.items():
                if key in where_params:
                    where_params[key]['value'] = value
        
        # 3. 生成新的WHERE条件
        new_where = self.where_engine.render(
            favorite['where_template'],
            where_params
        )
        
        # 4. 替换原始SQL中的WHERE部分
        new_sql = self._replace_where_clause(
            favorite['original_sql'],
            new_where
        )
        
        logger.info(f"执行收藏 {favorite_id}, SQL: {new_sql}")
        
        # 5. 执行SQL获取数据（这里需要调用NL2SQL服务或直接执行SQL）
        # 为了简化，我们直接执行SQL
        try:
            data_rows = self._execute_sql_query(new_sql)
            
            # 6. 使用原始算法参数执行算法
            algorithm_service = AlgorithmIntegrationService()
            
            # 构建算法请求
            algorithm_type = AlgorithmType(favorite['algorithm_type'])
            algorithm_params = favorite['algorithm_params']
            
            # 准备算法输入
            algorithm_request = {
                "data_rows": data_rows,
                "config": algorithm_params
            }
            
            # 执行算法
            from algorithm.executor.algorithm_executor import AlgorithmExecutor
            executor = AlgorithmExecutor()
            
            result = await executor.execute_algorithm(
                algorithm_type,
                algorithm_request
            )
            
            # 7. 保存执行历史
            self._save_execution_history(
                favorite_id=favorite_id,
                user_id=user_id,
                where_params=where_params,
                modified_where_params=modified_where_params if not use_original_params else None,
                executed_sql=new_sql,
                result=result
            )
            
            # 8. 更新收藏的执行统计
            self._update_execution_stats(favorite_id, where_params)
            
            return result
            
        except Exception as e:
            logger.error(f"执行收藏失败: {str(e)}", exc_info=True)
            
            # 保存失败的执行历史
            self._save_execution_history(
                favorite_id=favorite_id,
                user_id=user_id,
                where_params=where_params,
                modified_where_params=modified_where_params if not use_original_params else None,
                executed_sql=new_sql,
                result=None,
                error=str(e)
            )
            
            raise
    
    def _replace_where_clause(self, original_sql: str, new_where: str) -> str:
        """
        替换SQL中的WHERE子句
        
        Args:
            original_sql: 原始SQL
            new_where: 新的WHERE条件
        
        Returns:
            new_sql: 替换后的SQL
        """
        import re
        
        # 使用正则表达式找到WHERE子句
        # 匹配 WHERE ... (GROUP BY|ORDER BY|LIMIT|$)
        pattern = r'WHERE\s+(.+?)(?=\s+(?:GROUP BY|ORDER BY|LIMIT|$))'
        
        def replace_func(match):
            return f"WHERE {new_where}"
        
        new_sql = re.sub(pattern, replace_func, original_sql, flags=re.IGNORECASE | re.DOTALL)
        
        return new_sql
    
    def _execute_sql_query(self, sql: str) -> list:
        """
        执行SQL查询
        
        Args:
            sql: SQL语句
        
        Returns:
            data_rows: 查询结果
        """
        try:
            with self.db.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
                return results
        except Exception as e:
            logger.error(f"执行SQL失败: {sql}, {str(e)}")
            raise
    
    def _save_execution_history(self, favorite_id: int, user_id: int,
                                where_params: dict, modified_where_params: dict,
                                executed_sql: str, result: dict = None,
                                error: str = None):
        """
        保存执行历史
        
        Args:
            favorite_id: 收藏ID
            user_id: 用户ID
            where_params: WHERE参数
            modified_where_params: 修改的WHERE参数
            executed_sql: 执行的SQL
            result: 执行结果
            error: 错误信息
        """
        try:
            with self.db.cursor() as cursor:
                # 提取结果摘要
                result_summary = None
                data_rows_count = 0
                execution_time_ms = 0
                
                if result:
                    if isinstance(result, dict):
                        result_summary = {
                            'algorithm_type': result.get('algorithm_type'),
                            'status': result.get('status'),
                        }
                        # 根据不同算法类型提取关键信息
                        if 'k_used' in result:
                            result_summary['k_used'] = result['k_used']
                        if 'cluster_sizes' in result:
                            result_summary['cluster_sizes'] = result['cluster_sizes']
                        
                        execution_time_ms = result.get('execution_time_ms', 0)
                
                sql = """
                    INSERT INTO favorite_execution_history (
                        favorite_id, user_id, where_params, modified_where_params,
                        executed_sql, execution_status, execution_time_ms,
                        data_rows_count, result_summary, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql, (
                    favorite_id,
                    user_id,
                    json.dumps(where_params, ensure_ascii=False),
                    json.dumps(modified_where_params, ensure_ascii=False) if modified_where_params else None,
                    executed_sql,
                    'success' if result else 'failed',
                    execution_time_ms,
                    data_rows_count,
                    json.dumps(result_summary, ensure_ascii=False) if result_summary else None,
                    error
                ))
                self.db.commit()
                
                logger.info(f"执行历史已保存，收藏ID: {favorite_id}")
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"保存执行历史失败: {str(e)}", exc_info=True)
    
    def _update_execution_stats(self, favorite_id: int, where_params: dict):
        """
        更新收藏的执行统计
        
        Args:
            favorite_id: 收藏ID
            where_params: WHERE参数
        """
        try:
            with self.db.cursor() as cursor:
                sql = """
                    UPDATE user_favorites
                    SET execution_count = execution_count + 1,
                        last_executed_at = NOW(),
                        last_where_params = %s
                    WHERE id = %s
                """
                cursor.execute(sql, (
                    json.dumps(where_params, ensure_ascii=False),
                    favorite_id
                ))
                self.db.commit()
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新执行统计失败: {str(e)}", exc_info=True)
    
    def get_execution_history(self, favorite_id: int, user_id: int,
                             page: int = 1, page_size: int = 20) -> dict:
        """
        获取执行历史
        
        Args:
            favorite_id: 收藏ID
            user_id: 用户ID
            page: 页码
            page_size: 每页数量
        
        Returns:
            result: {items: [], total: int, page: int, pageSize: int}
        """
        try:
            with self.db.cursor() as cursor:
                # 查询总数
                count_sql = """
                    SELECT COUNT(*) as total
                    FROM favorite_execution_history
                    WHERE favorite_id = %s AND user_id = %s
                """
                cursor.execute(count_sql, (favorite_id, user_id))
                total = cursor.fetchone()['total']
                
                # 查询列表
                offset = (page - 1) * page_size
                list_sql = """
                    SELECT id as execution_id, executed_at, modified_where_params,
                           execution_status, execution_time_ms, data_rows_count,
                           result_summary
                    FROM favorite_execution_history
                    WHERE favorite_id = %s AND user_id = %s
                    ORDER BY executed_at DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(list_sql, (favorite_id, user_id, page_size, offset))
                items = cursor.fetchall()
                
                # 解析JSON字段
                for item in items:
                    if item['modified_where_params']:
                        item['modified_where_params'] = json.loads(item['modified_where_params'])
                    if item['result_summary']:
                        item['result_summary'] = json.loads(item['result_summary'])
                
                return {
                    'items': items,
                    'total': total,
                    'page': page,
                    'pageSize': page_size
                }
                
        except Exception as e:
            logger.error(f"获取执行历史失败: {str(e)}", exc_info=True)
            raise
