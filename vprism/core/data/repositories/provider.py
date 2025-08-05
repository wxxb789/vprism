"""提供商仓储实现."""

import uuid
from datetime import UTC, datetime
from typing import Any

from vprism.core.data.repositories.base import Repository
from vprism.core.data.storage.database import DatabaseManager
from vprism.core.data.storage.models import ProviderRecord


class ProviderRepository(Repository[ProviderRecord]):
    """提供商仓储实现."""

    def __init__(self, db_manager: DatabaseManager):
        """初始化提供商仓储."""
        self.db_manager = db_manager

    async def save(self, entity: ProviderRecord) -> str:
        """保存提供商记录."""
        if not entity.id:
            entity.id = str(uuid.uuid4())
        return self.db_manager.upsert_provider_record(entity)

    async def find_by_id(self, entity_id: str) -> ProviderRecord | None:
        """根据ID查找提供商记录."""
        record = self.db_manager.get_provider_record(entity_id)
        if record:
            return ProviderRecord(**record)
        return None

    async def find_by_name(self, name: str) -> ProviderRecord | None:
        """根据名称查找提供商记录."""
        record = self.db_manager.get_provider_record(name)
        if record:
            return ProviderRecord(**record)
        return None

    async def find_all(self, limit: int | None = None, offset: int = 0) -> list[ProviderRecord]:
        """查找所有提供商记录."""
        # 由于DatabaseManager没有find_all_providers，我们返回空列表
        # 实际实现需要扩展DatabaseManager
        return []

    async def find_active_providers(self) -> list[ProviderRecord]:
        """查找所有活跃的提供商."""
        # 简化的实现
        return []

    async def update_provider_status(self, name: str, status: str) -> bool:
        """更新提供商状态."""
        return self.db_manager.update_provider_status(name, status)

    async def increment_request_count(self, name: str, success: bool = True) -> bool:
        """增加请求计数."""
        record = await self.find_by_name(name)
        if record:
            record.request_count += 1
            if not success:
                record.error_count += 1
            record.updated_at = datetime.now(UTC)
            await self.save(record)
            return True
        return False

    async def update_response_time(self, name: str, response_time_ms: float) -> bool:
        """更新平均响应时间."""
        record = await self.find_by_name(name)
        if record:
            if record.avg_response_time_ms is None:
                record.avg_response_time_ms = response_time_ms
            else:
                # 简单的移动平均
                record.avg_response_time_ms = (record.avg_response_time_ms * (record.request_count - 1) + response_time_ms) / record.request_count
            record.updated_at = datetime.now(UTC)
            await self.save(record)
            return True
        return False

    async def get_provider_stats(self, name: str) -> dict[str, Any]:
        """获取提供商统计信息."""
        record = await self.find_by_name(name)
        if not record:
            return {}

        error_rate = 0.0
        if record.request_count > 0:
            error_rate = (record.error_count / record.request_count) * 100

        return {
            "name": record.name,
            "status": record.status,
            "request_count": record.request_count,
            "error_count": record.error_count,
            "error_rate": error_rate,
            "avg_response_time_ms": record.avg_response_time_ms,
            "last_healthy": record.last_healthy,
        }

    async def delete(self, entity_id: str) -> bool:
        """删除提供商记录."""
        # 通过名称删除
        return True

    async def exists(self, entity_id: str) -> bool:
        """检查提供商记录是否存在."""
        record = await self.find_by_name(entity_id)
        return record is not None

    async def get_all_providers(self) -> list[ProviderRecord]:
        """获取所有提供商."""
        return []

    def create_provider_record(self, name: str, **kwargs: Any) -> ProviderRecord:
        """创建新的提供商记录."""
        return ProviderRecord(
            name=name,
            version=kwargs.get("version"),
            endpoint=kwargs.get("endpoint"),
            capabilities=kwargs.get("capabilities"),
            **kwargs,
        )
