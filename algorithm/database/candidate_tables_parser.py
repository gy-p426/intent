"""用于解析/重建 NL2SQL 候选表的工具。

NL2SQL query-db 返回 `candidateTables: List[str]`，每个项目通常编码为：

"表名||表注释||PK:主键||FK:外键||||列名||列注释||数据类型||列名2||列注释2||数据类型2||..."

该模块提供容错解析和重建的辅助工具，以便后端可以：
- 向前端展示模式选项（表注释 / 列注释 / 数据类型）
- 根据用户选择的列重建 candidateTables
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class ColumnInfo:
    table_name: str
    table_comment: str
    column_name: str
    column_comment: str
    data_type: str


@dataclass(frozen=True)
class TableInfo:
    table_name: str
    table_comment: str
    columns: Tuple[ColumnInfo, ...]


def _safe_split(text: str, sep: str) -> List[str]:
    return [p for p in text.split(sep) if p is not None]


def parse_candidate_table_item(item: str) -> Optional[TableInfo]:
    """解析单个 candidateTables 项字符串。
    如果无法解析，则返回 None。
    """
    if not item or not isinstance(item, str):
        return None

    # 将表头和列部分分开。
    parts = item.split("||||", 1)
    header = parts[0]
    cols_part = parts[1] if len(parts) > 1 else ""

    header_parts = [p.strip() for p in header.split("||") if p is not None]
    if len(header_parts) < 1:
        return None

    table_name = header_parts[0].strip()
    if not table_name:
        return None

    table_comment = header_parts[1].strip() if len(header_parts) > 1 else ""

    col_tokens = [t.strip() for t in cols_part.split("||") if t is not None and t.strip()]

    # 通常被分组为（列名，列注释，数据类型，...）
    columns: List[ColumnInfo] = []
    i = 0
    while i < len(col_tokens):
        col_name = col_tokens[i].strip()
        col_comment = col_tokens[i + 1].strip() if i + 1 < len(col_tokens) else ""
        data_type = col_tokens[i + 2].strip() if i + 2 < len(col_tokens) else ""
        if col_name:
            columns.append(
                ColumnInfo(
                    table_name=table_name,
                    table_comment=table_comment,
                    column_name=col_name,
                    column_comment=col_comment,
                    data_type=data_type,
                )
            )
        i += 3

    return TableInfo(table_name=table_name, table_comment=table_comment, columns=tuple(columns))


def parse_candidate_tables(candidate_tables: Iterable[str]) -> List[TableInfo]:
    """将 candidateTables 列表解析为结构化的 TableInfo 列表。"""
    results: List[TableInfo] = []
    for item in candidate_tables or []:
        parsed = parse_candidate_table_item(item)
        if parsed is not None:
            results.append(parsed)
    return results


def flatten_columns(tables: Iterable[TableInfo]) -> List[ColumnInfo]:
    cols: List[ColumnInfo] = []
    for t in tables:
        cols.extend(list(t.columns))
    return cols


def build_candidate_table_item(table_name: str, table_comment: str, columns: Iterable[ColumnInfo]) -> str:
    """构建一个 candidateTables 项字符串。
    保留传统的分隔符结构，并将主键/外键占位符留空，因为手动选择只需要表/列/注释/类型。
    """
    header = f"{table_name}||{table_comment}||PK:||FK:"  # placeholders

    col_tokens: List[str] = []
    for c in columns:
        col_tokens.extend([c.column_name or "", c.column_comment or "", c.data_type or ""])

    # Ensure we always have columns section delimiter even if no columns.
    cols_part = "||".join(col_tokens)
    return f"{header}||||{cols_part}" if cols_part else f"{header}||||"


def rebuild_candidate_tables_from_selected_columns(
    selected_columns: Iterable[Dict[str, Any]],
    table_comment_by_name: Optional[Dict[str, str]] = None,
    column_meta_by_fqn: Optional[Dict[Tuple[str, str], Dict[str, str]]] = None,
) -> List[str]:
    """从选定的列重建 candidateTables。

    参数:
    selected_columns: 包含至少 {table_name, column_name} 的字典的可迭代对象。
    可选包含 column_comment/data_type。
    table_comment_by_name: 可选映射，用于填写 table_comment。
    column_meta_by_fqn: 可选映射 (table_name, column_name) -> {column_comment, data_type}。

    返回:
    candidateTables 列表 (List[str])
    """
    table_comment_by_name = table_comment_by_name or {}
    column_meta_by_fqn = column_meta_by_fqn or {}

    grouped: Dict[str, List[ColumnInfo]] = {}

    for item in selected_columns or []:
        if not isinstance(item, dict):
            continue
        table_name = str(item.get("table_name") or item.get("table") or "").strip()
        column_name = str(item.get("column_name") or item.get("column") or "").strip()
        if not table_name or not column_name:
            continue

        table_comment = str(item.get("table_comment") or table_comment_by_name.get(table_name, "") or "")

        meta = column_meta_by_fqn.get((table_name, column_name), {})
        column_comment = str(item.get("column_comment") or item.get("comment") or meta.get("column_comment") or "")
        data_type = str(item.get("data_type") or item.get("type") or meta.get("data_type") or "")

        grouped.setdefault(table_name, []).append(
            ColumnInfo(
                table_name=table_name,
                table_comment=table_comment,
                column_name=column_name,
                column_comment=column_comment,
                data_type=data_type,
            )
        )

    candidate_tables: List[str] = []
    for table_name, cols in grouped.items():
        # 使用第一列的 table_comment（应该都是相同的）
        table_comment = cols[0].table_comment if cols else table_comment_by_name.get(table_name, "")
        candidate_tables.append(build_candidate_table_item(table_name, table_comment, cols))

    return candidate_tables
