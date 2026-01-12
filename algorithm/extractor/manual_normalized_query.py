"""Manual normalized_query generator.

This module builds prompts to regenerate normalized_query based on user-selected
schema mapping in manual DB selection flow.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def build_manual_normalized_query_messages(
    *,
    original_question: str,
    algorithm_type: str,
    manual_parameter_mapping: Dict[str, Any],
    user_feedback: Optional[str] = None,
) -> List[Dict[str, str]]:
    mapping_json = json.dumps(manual_parameter_mapping, ensure_ascii=False, indent=2)

    system = f"""你是一个数据分析助手，负责把用户问题规范化成可用于 NL2SQL 的中文查询描述（normalized_query）.
    
    生成的中文查询描述(normalized_query)中一定写明返回的数据列注释，并且标名返回哪几列数据，否则无法正确解析，如"获取客户ID、流失状态、年龄、月使用量，返回客户ID、流失状态、年龄、月使用量共4列数据"！！！
    normalized_query一定要包含将用户选择的所有字段，必须体现用户选择的字段含义（优先使用 column_comment，其次 column_name）。
    尽量保持简洁明确，避免歧义
    
    输出JSON示例：
    {{
        "normalized_query": "获取客户数据的客户ID、流失状态、年龄、月使用量，返回客户ID、流失状态、年龄、月使用量共4列数据"
    }}
"""

    user = (
        f"用户原始问题：{original_question}\n"
        # f"算法类型：{algorithm_type}\n"
        f"用户选择的字段映射（JSON）：\n{mapping_json}\n"
    )
    if user_feedback:
        user += f"用户补充说明：{user_feedback}\n"

    user += "请生成 normalized_query："

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
