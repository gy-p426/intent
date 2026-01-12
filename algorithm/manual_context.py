"""手动流程上下文存储。

手动数据库选择流程跨越多个 HTTP 请求。
此模块提供一个带 TTL 的最小内存上下文存储。

注意：对于多实例部署，应使用共享存储（例如 Redis）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass
class ManualFlowContext:
    created_at: datetime
    question: str
    window_id: str
    session_id: str
    algorithm_type: Any
    parameters: Any
    candidate_tables: Any
    keywords: Any


class ManualContextStore:
    def __init__(self, ttl_seconds: int = 30 * 60):
        self._ttl = timedelta(seconds=ttl_seconds)
        self._data: Dict[str, ManualFlowContext] = {}

    def set(self, token: str, ctx: ManualFlowContext) -> None:
        self._data[token] = ctx

    def get(self, token: str) -> Optional[ManualFlowContext]:
        self._cleanup_expired()
        return self._data.get(token)

    def pop(self, token: str) -> Optional[ManualFlowContext]:
        self._cleanup_expired()
        return self._data.pop(token, None)

    def _cleanup_expired(self) -> None:
        now = datetime.utcnow()
        expired = [k for k, v in self._data.items() if (now - v.created_at) > self._ttl]
        for k in expired:
            self._data.pop(k, None)
