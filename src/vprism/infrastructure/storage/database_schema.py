"""优化的数据库表结构设计"""

import logging

import duckdb

logger = logging.getLogger(__name__)


class DatabaseSchema:
    """优化的数据库表结构设计和管理"""

    def __init__(self, db_path: str = "vprism_data.duckdb"):
        """初始化数据库连接和表结构"""
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self) -> None:
        """建立数据库连接"""
        try:
            self.conn = duckdb.connect(self.db_path)
            logger.info(f"Connected to DuckDB database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def _create_tables(self) -> None:
        """创建优化的数据库表结构"""
        # 资产信息表 - 复合主键优化
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_info (
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(8) NOT NULL,
                name VARCHAR(256),
                asset_type VARCHAR(16) NOT NULL,
                currency VARCHAR(8),
                exchange VARCHAR(16),
                sector VARCHAR(64),
                industry VARCHAR(128),
                is_active BOOLEAN DEFAULT TRUE,
                provider VARCHAR(32) NOT NULL,
                exchange_timezone VARCHAR(32),
                first_traded DATE,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON,
                PRIMARY KEY (symbol, market)
            )
        """)

        # 日线OHLCV数据表 - 时间分区优化
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_ohlcv (
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(8) NOT NULL,
                trade_date DATE NOT NULL,
                open_price DECIMAL(18,6) NOT NULL,
                high_price DECIMAL(18,6) NOT NULL,
                low_price DECIMAL(18,6) NOT NULL,
                close_price DECIMAL(18,6) NOT NULL,
                volume DECIMAL(20,2) NOT NULL,
                amount DECIMAL(20,2),
                adjusted_close DECIMAL(18,6),
                split_factor DECIMAL(10,6) DEFAULT 1.0,
                dividend_amount DECIMAL(18,6) DEFAULT 0.0,
                provider VARCHAR(32) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, market, trade_date)
            )
        """)

        # 分钟级数据表 - 基于时间框架分区
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS intraday_ohlcv (
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(8) NOT NULL,
                timeframe VARCHAR(8) NOT NULL, -- 1m, 5m, 15m, 1h, 4h
                timestamp TIMESTAMP NOT NULL,
                open_price DECIMAL(18,6) NOT NULL,
                high_price DECIMAL(18,6) NOT NULL,
                low_price DECIMAL(18,6) NOT NULL,
                close_price DECIMAL(18,6) NOT NULL,
                volume DECIMAL(20,2) NOT NULL,
                amount DECIMAL(20,2),
                provider VARCHAR(32) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, market, timeframe, timestamp)
            )
        """)

        # 实时行情数据表 - 最新价格快照
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS real_time_quotes (
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(8) NOT NULL,
                price DECIMAL(18,6) NOT NULL,
                change_amount DECIMAL(18,6),
                change_percent DECIMAL(8,4),
                volume DECIMAL(20,2),
                bid DECIMAL(18,6),
                ask DECIMAL(18,6),
                bid_size DECIMAL(20,2),
                ask_size DECIMAL(20,2),
                timestamp TIMESTAMP NOT NULL,
                provider VARCHAR(32) NOT NULL,
                PRIMARY KEY (symbol, market)
            )
        """)

        # 通用缓存表 - 存储非结构化数据
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key VARCHAR(32) PRIMARY KEY,
                data_type VARCHAR(16) NOT NULL, -- ohlcv, quote, fundamental, etc.
                data_json JSON NOT NULL,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 数据质量表 - 存储数据质量指标
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS data_quality (
                symbol VARCHAR(32) NOT NULL,
                market VARCHAR(8) NOT NULL,
                date_range_start DATE,
                date_range_end DATE,
                completeness_score DECIMAL(5,2),
                accuracy_score DECIMAL(5,2),
                consistency_score DECIMAL(5,2),
                total_records INTEGER,
                missing_records INTEGER,
                anomaly_count INTEGER,
                provider VARCHAR(32) NOT NULL,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, market, date_range_start, date_range_end)
            )
        """)

        # 数据源状态表 - 跟踪数据源健康状况
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_status (
                provider_name VARCHAR(32) PRIMARY KEY,
                status VARCHAR(16) NOT NULL, -- healthy, degraded, down
                last_success TIMESTAMP,
                last_failure TIMESTAMP,
                failure_reason TEXT,
                uptime_percent DECIMAL(5,2),
                avg_response_time_ms INTEGER,
                requests_count INTEGER DEFAULT 0,
                failures_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建优化的索引
        self._create_indexes()

        logger.info("Database tables created successfully")

    def _create_indexes(self) -> None:
        """创建性能优化的索引"""

        # 资产信息表索引
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_type ON asset_info(asset_type)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_market ON asset_info(market)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_active ON asset_info(is_active)"
        )

        # 日线数据表索引 - 支持按日期和符号的快速查询
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_ohlcv(trade_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_symbol_date ON "
            "daily_ohlcv(symbol, trade_date DESC)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_market_date ON "
            "daily_ohlcv(market, trade_date DESC)"
        )

        # 分钟级数据表索引 - 支持时间范围查询
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_intraday_timeframe ON "
            "intraday_ohlcv(timeframe)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_intraday_symbol_timeframe ON "
            "intraday_ohlcv(symbol, timeframe, timestamp DESC)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_intraday_timestamp ON "
            "intraday_ohlcv(timestamp)"
        )

        # 实时报价表索引
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quotes_timestamp ON "
            "real_time_quotes(timestamp DESC)"
        )

        # 缓存表索引 - 支持过期清理
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_data_type ON cache_entries(data_type)"
        )

        # 数据质量表索引
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quality_date ON "
            "data_quality(date_range_start, date_range_end)"
        )

        logger.info("Database indexes created successfully")

    def create_partitioned_tables(self) -> None:
        """创建分区表以支持大数据量"""

        # 为日线数据创建按年份的视图
        self.conn.execute("""
            CREATE OR REPLACE VIEW daily_ohlcv_2024 AS
            SELECT * FROM daily_ohlcv
            WHERE trade_date >= '2024-01-01' AND trade_date < '2025-01-01'
        """)

        self.conn.execute("""
            CREATE OR REPLACE VIEW daily_ohlcv_2023 AS
            SELECT * FROM daily_ohlcv
            WHERE trade_date >= '2023-01-01' AND trade_date < '2024-01-01'
        """)

        logger.info("Partitioned views created successfully")

    def create_materialized_views(self) -> None:
        """创建物化视图以优化常用查询"""

        # 最新价格视图
        self.conn.execute("""
            CREATE OR REPLACE VIEW latest_prices AS
            SELECT DISTINCT ON (symbol, market)
                symbol,
                market,
                close_price as price,
                volume,
                trade_date,
                provider
            FROM daily_ohlcv
            ORDER BY symbol, market, trade_date DESC
        """)

        # 月度统计视图
        self.conn.execute("""
            CREATE OR REPLACE VIEW monthly_stats AS
            SELECT
                symbol,
                market,
                DATE_TRUNC('month', trade_date) as month,
                MIN(low_price) as min_price,
                MAX(high_price) as max_price,
                AVG(close_price) as avg_price,
                SUM(volume) as total_volume,
                COUNT(*) as trading_days
            FROM daily_ohlcv
            GROUP BY symbol, market, DATE_TRUNC('month', trade_date)
        """)

        logger.info("Materialized views created successfully")

    def optimize_tables(self) -> None:
        """优化表性能"""

        # 分析表统计信息
        tables = [
            "asset_info",
            "daily_ohlcv",
            "intraday_ohlcv",
            "real_time_quotes",
            "cache_entries",
            "data_quality",
        ]

        for table in tables:
            try:
                self.conn.execute(f"ANALYZE {table}")
                logger.debug(f"Analyzed table: {table}")
            except Exception as e:
                logger.warning(f"Failed to analyze table {table}: {e}")

        logger.info("Database tables optimized successfully")

    def get_table_stats(self) -> dict:
        """获取表统计信息"""
        stats = {}

        tables = [
            "asset_info",
            "daily_ohlcv",
            "intraday_ohlcv",
            "real_time_quotes",
            "cache_entries",
            "data_quality",
        ]

        for table in tables:
            try:
                result = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                stats[table] = result[0] if result else 0
            except Exception:
                stats[table] = 0

        return stats

    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __del__(self):
        """析构函数"""
        self.close()


class DatabaseMigration:
    """数据库迁移工具"""

    def __init__(self, db_path: str):
        """初始化迁移工具"""
        self.db_path = db_path
        self.schema = DatabaseSchema(db_path)

    def migrate_v1_to_v2(self) -> None:
        """从版本1迁移到版本2"""
        conn = duckdb.connect(self.db_path)

        # 添加新列
        try:
            conn.execute(
                "ALTER TABLE daily_ohlcv ADD COLUMN adjusted_close DECIMAL(18,6)"
            )
            conn.execute(
                "ALTER TABLE daily_ohlcv ADD COLUMN split_factor DECIMAL(10,6) "
                "DEFAULT 1.0"
            )
            conn.execute(
                "ALTER TABLE daily_ohlcv ADD COLUMN dividend_amount DECIMAL(18,6) "
                "DEFAULT 0.0"
            )
            logger.info("Migration v1 to v2 completed")
        except Exception as e:
            logger.warning(f"Migration already applied or failed: {e}")
        finally:
            conn.close()

    def setup_test_data(self) -> None:
        """设置测试数据"""
        conn = duckdb.connect(self.db_path)

        # 插入测试资产
        conn.execute("""
            INSERT OR IGNORE INTO asset_info
            (symbol, market, name, asset_type, currency, exchange)
            VALUES
                ('000001.SZ', 'cn', '平安银行', 'stock', 'CNY', 'SZSE'),
                ('AAPL', 'us', 'Apple Inc.', 'stock', 'USD', 'NASDAQ'),
                ('BTCUSDT', 'crypto', 'Bitcoin', 'crypto', 'USDT', 'BINANCE')
        """)

        # 插入测试日线数据
        conn.execute("""
            INSERT OR IGNORE INTO daily_ohlcv
            (symbol, market, trade_date, open_price, high_price, low_price,
             close_price, volume, provider)
            VALUES
                ('000001.SZ', 'cn', '2024-01-01', 10.50, 10.80, 10.30,
                 10.60, 1000000, 'tushare'),
                ('000001.SZ', 'cn', '2024-01-02', 10.60, 10.90, 10.40,
                 10.75, 1200000, 'tushare'),
                ('AAPL', 'us', '2024-01-01', 150.00, 152.00, 149.50,
                 151.50, 50000000, 'yahoo')
        """)

        conn.close()
        logger.info("Test data setup completed")
