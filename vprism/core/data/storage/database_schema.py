"""数据库迁移和测试数据设置工具"""

from datetime import datetime, timedelta

from vprism.core.data.storage.schema import DatabaseSchema


class DatabaseMigration:
    """数据库迁移工具类"""

    def __init__(self, db_path: str = "data/vprism.db"):
        """初始化迁移工具"""
        self.db_path = db_path
        self.schema = DatabaseSchema(db_path)

    def migrate_v1_to_v2(self) -> None:
        """从v1版本迁移到v2版本

        v1到v2的主要变更：
        1. 添加数据质量表
        2. 添加提供商状态表
        3. 优化索引
        """
        print("开始迁移数据库从v1到v2...")

        # 检查是否已经是最新版本
        try:
            self.schema.conn.execute("SELECT * FROM data_quality LIMIT 1")
            print("数据库已经是v2版本，无需迁移")
            return
        except Exception:
            pass

        # 创建缺失的表（在schema.py中应该已经定义）
        print("创建数据质量表...")
        self.schema._create_tables()

        print("创建物化视图...")
        self.schema.create_materialized_views()

        print("创建分区表...")
        self.schema.create_partitioned_tables()

        print("优化表结构...")
        self.schema.optimize_tables()

        print("数据库迁移完成")

    def setup_test_data(self) -> None:
        """设置测试数据"""
        print("开始设置测试数据...")

        try:
            # 插入测试资产信息
            self.schema.conn.execute("""
                INSERT OR IGNORE INTO asset_info
                (id, symbol, market, name, asset_type, currency, exchange, provider)
                VALUES
                ('asset-001', '000001.SZ', 'cn', '平安银行', 'stock', 'CNY', 'SZSE', 'tushare'),
                ('asset-002', '000002.SZ', 'cn', '万科A', 'stock', 'CNY', 'SZSE', 'tushare'),
                ('asset-003', '600000.SH', 'cn', '浦发银行', 'stock', 'CNY', 'SSE', 'tushare'),
                ('asset-004', 'AAPL', 'us', 'Apple Inc.', 'stock', 'USD', 'NASDAQ', 'yfinance'),
                ('asset-005', 'MSFT', 'us', 'Microsoft Corporation', 'stock', 'USD', 'NASDAQ', 'yfinance')
            """)

            # 插入测试日线数据
            base_date = datetime(2024, 1, 1)
            for i in range(30):  # 30天的数据
                date_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                self.schema.conn.execute(
                    """
                    INSERT OR IGNORE INTO daily_ohlcv
                    (id, symbol, market, trade_date, open_price, high_price, low_price, close_price, volume, provider)
                    VALUES
                    (?, '000001.SZ', 'cn', ?, 10.0 + ?, 10.5 + ?, 9.5 + ?, 10.2 + ?, 1000000 + ? * 10000, 'tushare')
                """,
                    (f"daily-{i:04d}", date_str, i * 0.01, i * 0.01, i * 0.01, i * 0.01, i * 100),
                )

            # 插入测试提供商状态
            self.schema.conn.execute("""
                INSERT OR IGNORE INTO provider_status
                (id, provider_name, status, last_success, uptime_percent, avg_response_time_ms)
                VALUES
                ('provider-001', 'tushare', 'healthy', CURRENT_TIMESTAMP, 99.5, 150),
                ('provider-002', 'yfinance', 'healthy', CURRENT_TIMESTAMP, 98.8, 200),
                ('provider-003', 'alpha_vantage', 'healthy', CURRENT_TIMESTAMP, 97.2, 300)
            """)

            # 插入测试数据质量记录
            self.schema.conn.execute("""
                INSERT OR IGNORE INTO data_quality
                (id, symbol, market, date_range_start, date_range_end, completeness_score, accuracy_score, consistency_score, total_records, provider)
                VALUES
                ('quality-001', '000001.SZ', 'cn', '2024-01-01', '2024-01-31', 98.5, 99.2, 97.8, 30, 'tushare'),
                ('quality-002', 'AAPL', 'us', '2024-01-01', '2024-01-31', 99.1, 98.9, 98.5, 30, 'yfinance')
            """)

            print("测试数据设置完成")

        except Exception as e:
            print(f"设置测试数据时出错: {e}")
            raise

    def cleanup_test_data(self) -> None:
        """清理测试数据"""
        print("清理测试数据...")

        try:
            # 删除测试数据
            tables = ["data_quality", "provider_status", "daily_ohlcv", "asset_info", "intraday_ohlcv", "real_time_quotes"]

            for table in tables:
                try:
                    self.schema.conn.execute(f"DELETE FROM {table}")
                except Exception as e:
                    print(f"清理表 {table} 时出错: {e}")

            print("测试数据清理完成")

        except Exception as e:
            print(f"清理测试数据时出错: {e}")
            raise

    def close(self) -> None:
        """关闭连接"""
        if hasattr(self, "schema"):
            self.schema.close()


def main() -> None:
    """命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库迁移和测试数据工具")
    parser.add_argument("command", choices=["migrate", "setup-test", "cleanup-test"])
    parser.add_argument("--db-path", default="data/vprism.db", help="数据库路径")

    args = parser.parse_args()

    migration = DatabaseMigration(args.db_path)

    try:
        if args.command == "migrate":
            migration.migrate_v1_to_v2()
        elif args.command == "setup-test":
            migration.setup_test_data()
        elif args.command == "cleanup-test":
            migration.cleanup_test_data()
    finally:
        migration.close()


if __name__ == "__main__":
    main()
