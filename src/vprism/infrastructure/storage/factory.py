"""数据仓储工厂模式实现"""

import os

from .repository import DataRepository, DuckDBRepository


class RepositoryFactory:
    """数据仓储工厂类"""

    _instance: DuckDBRepository | None = None

    @classmethod
    def create_repository(
        cls, db_path: str = None, use_memory: bool = False
    ) -> DataRepository:
        """
        创建数据仓储实例

        Args:
            db_path: 数据库文件路径，如果为None则使用环境变量或默认值
            use_memory: 是否使用内存数据库

        Returns:
            DataRepository实例
        """
        if use_memory:
            return DuckDBRepository(":memory:")

        if db_path is None:
            # 从环境变量获取，否则使用默认值
            db_path = os.getenv("VPRISM_DB_PATH", "vprism_data.duckdb")

        return DuckDBRepository(db_path)

    @classmethod
    def get_default_repository(cls) -> DataRepository:
        """获取默认仓储实例（单例模式）"""
        if cls._instance is None:
            cls._instance = cls.create_repository()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例实例（主要用于测试）"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None

    @classmethod
    def create_test_repository(cls) -> DataRepository:
        """创建测试用的内存仓储"""
        return cls.create_repository(use_memory=True)


# 便捷函数
def get_repository() -> DataRepository:
    """获取默认仓储实例"""
    return RepositoryFactory.get_default_repository()


def create_test_repository() -> DataRepository:
    """创建测试仓储实例"""
    return RepositoryFactory.create_test_repository()
