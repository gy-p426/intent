"""
WHERE条件模板引擎

负责解析和渲染WHERE条件模板
"""

import logging
import re
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class WhereTemplateEngine:
    """WHERE条件模板引擎"""

    def render(self, template: str, params: Dict[str, Dict[str, Any]]) -> str:
        """
        渲染WHERE条件模板

        Args:
            template: WHERE模板字符串
            params: 参数字典（包含value、type等信息）

        Returns:
            rendered_where: 渲染后的WHERE条件

        示例：
            template = "date BETWEEN '{start_date}' AND '{end_date}' AND department = '{department}'"
            params = {
                "start_date": {"value": "2025-01-01", "type": "date"},
                "end_date": {"value": "2025-12-31", "type": "date"},
                "department": {"value": "销售部", "type": "string"}
            }

            结果：
            "date BETWEEN '2025-01-01' AND '2025-12-31' AND department = '销售部'"
        """
        where_clause = template

        for key, param_config in params.items():
            placeholder = f"{{{key}}}"
            value = param_config.get('value')

            if placeholder in where_clause:
                # 根据类型处理值
                if param_config.get('type') == 'string':
                    # 字符串类型，保持引号
                    value_str = str(value)
                elif param_config.get('type') == 'date':
                    # 日期类型，保持引号
                    value_str = str(value)
                elif param_config.get('type') == 'integer':
                    # 整数类型，不需要引号
                    value_str = str(value)
                else:
                    value_str = str(value)

                where_clause = where_clause.replace(placeholder, value_str)

        return where_clause

    def extract_params_from_where(self, where_clause: str, table_name: str = None) -> Tuple[
        str, Dict[str, Dict[str, Any]], Dict[str, str]]:
        """
        从WHERE子句中提取可参数化的部分（Fallback方案）

        Args:
            where_clause: WHERE条件字符串
            table_name: 表名（用于生成options查询SQL）

        Returns:
            template: 参数化模板
            params: 参数字典（不含options）
            options_query_sqls: 查询options的SQL字典

        示例：
            where_clause = "date BETWEEN '2024-01-01' AND '2024-12-31' AND department = '技术部'"
            table_name = "t_performance"

            返回：
            template = "date BETWEEN '{start_date}' AND '{end_date}' AND department = '{department}'"
            params = {
                "start_date": {"value": "2024-01-01", "type": "date", "label": "开始日期"},
                "end_date": {"value": "2024-12-31", "type": "date", "label": "结束日期"},
                "department": {"value": "技术部", "type": "string", "label": "部门"}
            }
            options_query_sqls = {
                "department": "SELECT DISTINCT department FROM t_performance WHERE department IS NOT NULL ORDER BY department LIMIT 100"
            }
        """
        template = where_clause
        params = {}
        options_query_sqls = {}

        # 提取日期范围 (BETWEEN 'date1' AND 'date2')
        date_pattern = r"BETWEEN\s+'([^']+)'\s+AND\s+'([^']+)'"
        date_matches = list(re.finditer(date_pattern, where_clause))

        for i, match in enumerate(date_matches):
            start_date = match.group(1)
            end_date = match.group(2)

            start_key = f"start_date_{i}" if i > 0 else "start_date"
            end_key = f"end_date_{i}" if i > 0 else "end_date"

            template = template.replace(f"'{start_date}'", f"'{{{start_key}}}'", 1)
            template = template.replace(f"'{end_date}'", f"'{{{end_key}}}'", 1)

            params[start_key] = {"value": start_date, "type": "date", "label": "开始日期"}
            params[end_key] = {"value": end_date, "type": "date", "label": "结束日期"}
            # 日期类型不需要options_query_sql

        # 提取字符串等值条件 (column = 'value')
        string_pattern = r"(\w+)\s*=\s*'([^']+)'"
        string_matches = list(re.finditer(string_pattern, template))

        for match in string_matches:
            column = match.group(1)
            value = match.group(2)

            # 跳过已经参数化的部分
            if '{' in match.group(0):
                continue

            param_key = column
            template = template.replace(f"'{value}'", f"'{{{param_key}}}'", 1)

            params[param_key] = {
                "value": value,
                "type": "string",
                "label": column
            }

            # 为字符串类型生成options查询SQL
            if table_name:
                options_query_sqls[
                    param_key] = f"SELECT DISTINCT {column} FROM {table_name} WHERE {column} IS NOT NULL ORDER BY {column} LIMIT 100"

        logger.info(f"提取WHERE参数: {len(params)}个参数, {len(options_query_sqls)}个options查询")

        return template, params, options_query_sqls

    def extract_placeholders(self, template: str) -> list:
        """提取模板中的所有占位符"""
        return re.findall(r'\{(\w+)\}', template)
