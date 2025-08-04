"""数据库表结构和初始化."""

import os

import duckdb


class DatabaseSchema:
    """数据库表结构管理类，提供数据库初始化和表结构管理功能。"""

    def __init__(self, db_path: str = "data/vprism.db"):
        """
        初始化数据库模式。

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn = None
        self._initialize()

    def _initialize(self):
        """初始化数据库连接和表结构。"""
        # 确保数据目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir:  # 只在目录路径不为空时创建
            os.makedirs(db_dir, exist_ok=True)

        # 连接数据库
        self.conn = duckdb.connect(self.db_path)

        # 创建表结构
        self._create_tables()
        self._create_indexes()
        self._create_views()

    def _create_tables(self):
        """创建所有数据表。"""
        # 创建数据记录表（兼容旧表名）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_info (
                symbol VARCHAR NOT NULL,
                market VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                asset_type VARCHAR NOT NULL,
                currency VARCHAR DEFAULT 'CNY',
                exchange VARCHAR,
                sector VARCHAR,
                industry VARCHAR,
                is_active BOOLEAN DEFAULT TRUE,
                provider VARCHAR,
                exchange_timezone VARCHAR DEFAULT 'Asia/Shanghai',
                first_traded DATE,
                last_updated TIMESTAMP,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, market)
            )
        """)

        # 创建数据记录表（新表名，用于测试兼容性）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS data_records (
                id VARCHAR PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                asset_type VARCHAR NOT NULL,
                market VARCHAR,
                timestamp TIMESTAMP NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                timeframe VARCHAR,
                provider VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_ohlcv (
                id VARCHAR PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                market VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                open_price DOUBLE,
                high_price DOUBLE,
                low_price DOUBLE,
                close_price DOUBLE,
                adjusted_close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                provider VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS intraday_ohlcv (
                id VARCHAR PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                market VARCHAR NOT NULL,
                timeframe VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open_price DOUBLE,
                high_price DOUBLE,
                low_price DOUBLE,
                close_price DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                provider VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS real_time_quotes (
                id VARCHAR PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                market VARCHAR NOT NULL,
                price DOUBLE,
                bid DOUBLE,
                ask DOUBLE,
                bid_size DOUBLE,
                ask_size DOUBLE,
                change_amount DOUBLE,
                change_percent DOUBLE,
                volume BIGINT,
                timestamp TIMESTAMP NOT NULL,
                provider VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key VARCHAR PRIMARY KEY,
                data_hash VARCHAR NOT NULL,
                data_source VARCHAR,
                data_content BLOB,
                hit_count BIGINT DEFAULT 0,
                last_access TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                metadata JSON
            )
        """)

        # 创建缓存记录表（兼容测试）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_records (
                id VARCHAR PRIMARY KEY,
                cache_key VARCHAR NOT NULL,
                query_hash VARCHAR,
                data_source VARCHAR,
                hit_count BIGINT DEFAULT 0,
                last_access TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                metadata JSON
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS data_quality (
                id VARCHAR PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                market VARCHAR NOT NULL,
                date_range_start DATE,
                date_range_end DATE,
                completeness_score DOUBLE,
                accuracy_score DOUBLE,
                consistency_score DOUBLE,
                missing_records BIGINT,
                duplicate_records BIGINT,
                outlier_records BIGINT,
                anomaly_count BIGINT,
                total_records BIGINT,
                provider VARCHAR,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_status (
                provider_name VARCHAR PRIMARY KEY,
                status VARCHAR DEFAULT 'healthy',
                last_success TIMESTAMP,
                uptime_percent DOUBLE,
                avg_response_time_ms DOUBLE,
                request_count BIGINT DEFAULT 0,
                error_count BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建提供商记录表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_records (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                version VARCHAR,
                endpoint VARCHAR,
                status VARCHAR DEFAULT 'active',
                last_healthy TIMESTAMP,
                request_count BIGINT DEFAULT 0,
                error_count BIGINT DEFAULT 0,
                avg_response_time_ms DOUBLE,
                capabilities JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建查询记录表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS query_records (
                id VARCHAR PRIMARY KEY,
                query_hash VARCHAR,
                asset_type VARCHAR,
                market VARCHAR,
                symbols VARCHAR[],
                timeframe VARCHAR,
                start_date DATE,
                end_date DATE,
                provider VARCHAR,
                status VARCHAR DEFAULT 'pending',
                request_time_ms INTEGER,
                response_size INTEGER,
                cache_hit BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

    def _create_indexes(self):
        """创建数据库索引。"""
        # 资产信息表索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_symbol ON asset_info(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_market ON asset_info(market)")

        # 日线数据表索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_symbol ON daily_ohlcv(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_ohlcv(trade_date)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_symbol_date ON daily_ohlcv(symbol, trade_date)")

        # 分钟数据表索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_intraday_symbol ON intraday_ohlcv(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_intraday_timestamp ON intraday_ohlcv(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_intraday_symbol_timeframe ON intraday_ohlcv(symbol, timeframe)")

        # 实时报价索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_quotes_symbol ON real_time_quotes(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_quotes_timestamp ON real_time_quotes(timestamp)")

        # 缓存索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_key ON cache_entries(cache_key)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_source ON cache_entries(data_source)")

        # 数据质量索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_quality_symbol ON data_quality(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_quality_date ON data_quality(date_range_start, date_range_end)")

        # 提供商状态索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_status ON provider_status(provider_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_last_success ON provider_status(last_success)")

        # 数据记录表索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_data_records_symbol ON data_records(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_data_records_timestamp ON data_records(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_data_records_provider ON data_records(provider)")

        # 缓存记录表索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_records_key ON cache_records(cache_key)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_records_expires ON cache_records(expires_at)")

        # 提供商记录表索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_records_name ON provider_records(name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_records_status ON provider_records(status)")

        # 查询记录表索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_query_records_hash ON query_records(query_hash)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_query_records_status ON query_records(status)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_query_records_created ON query_records(created_at)")

    def _create_views(self):
        """创建数据库视图。"""
        # 最新价格视图
        self.conn.execute("""
            CREATE OR REPLACE VIEW latest_prices AS
            SELECT 
                a.symbol,
                a.market,
                a.name,
                d.close_price as latest_close,
                d.trade_date as latest_date,
                d.volume as latest_volume,
                d.provider
            FROM asset_info a
            LEFT JOIN daily_ohlcv d ON a.symbol = d.symbol AND a.market = d.market
            WHERE d.trade_date = (SELECT MAX(trade_date) FROM daily_ohlcv WHERE symbol = a.symbol AND market = a.market)
        """)

        # 月度统计视图
        self.conn.execute("""
            CREATE OR REPLACE VIEW monthly_stats AS
            SELECT 
                symbol,
                market,
                DATE_TRUNC('month', trade_date) as month,
                COUNT(*) as trading_days,
                AVG(close_price) as avg_close,
                MIN(low_price) as min_low,
                MAX(high_price) as max_high,
                SUM(volume) as total_volume,
                MIN(close_price) as min_close,
                MAX(close_price) as max_close
            FROM daily_ohlcv
            GROUP BY symbol, market, DATE_TRUNC('month', trade_date)
            ORDER BY symbol, market, month DESC
        """)

        # 缓存统计视图
        self.conn.execute("""
            CREATE OR REPLACE VIEW cache_statistics AS
            SELECT 
                data_source,
                COUNT(*) as total_entries,
                SUM(hit_count) as total_hits,
                AVG(hit_count) as avg_hits_per_entry,
                COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 END) as active_entries,
                COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 END) as expired_entries
            FROM cache_entries
            GROUP BY data_source
        """)

        # 数据质量统计视图
        self.conn.execute("""
            CREATE OR REPLACE VIEW data_quality_summary AS
            SELECT 
                provider,
                AVG(completeness_score) as avg_completeness,
                AVG(accuracy_score) as avg_accuracy,
                AVG(consistency_score) as avg_consistency,
                COUNT(*) as total_symbols,
                SUM(total_records) as total_records
            FROM data_quality
            GROUP BY provider
        """)

    def create_materialized_views(self):
        """创建物化视图。"""
        # 创建物化视图以提高查询性能
        try:
            self.conn.execute("""
                CREATE OR REPLACE TABLE latest_prices_materialized AS
                SELECT * FROM latest_prices
            """)
        except Exception:
            # 如果物化视图已存在则跳过
            pass

    def create_partitioned_tables(self):
        """创建分区表。"""
        # 创建按年份分区的表
        current_year = 2024
        for year in [current_year, current_year - 1]:
            try:
                self.conn.execute(f"""
                    CREATE OR REPLACE TABLE daily_ohlcv_{year} AS
                    SELECT * FROM daily_ohlcv 
                    WHERE EXTRACT(YEAR FROM trade_date) = {year}
                """)
            except Exception:
                # 如果分区表已存在则跳过
                pass

    def get_table_stats(self) -> dict[str, int]:
        """
        获取表统计信息。

        Returns:
            表名到记录数的映射字典
        """
        tables = ["asset_info", "daily_ohlcv", "intraday_ohlcv", "real_time_quotes", "cache_entries", "data_quality"]

        stats = {}
        for table in tables:
            try:
                result = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                stats[table] = result[0] if result else 0
            except Exception:
                stats[table] = 0

        return stats

    def optimize_tables(self):
        """优化表性能。"""
        try:
            # 执行VACUUM操作
            self.conn.execute("CHECKPOINT")

            # 更新统计信息
            self.conn.execute("ANALYZE")

        except Exception:
            # 如果优化失败，不影响主要功能
            pass

    def close(self):
        """关闭数据库连接。"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.close()


def initialize_database(db_path: str = "data/vprism.db") -> duckdb.DuckDBPyConnection:
    """初始化数据库表结构（向后兼容）。"""
    schema = DatabaseSchema(db_path)
    return schema.conn


def create_views(conn: duckdb.DuckDBPyConnection) -> None:
    """创建数据库视图（向后兼容）。"""
    schema = DatabaseSchema()
    schema.conn = conn


def setup_database(db_path: str = "data/vprism.db") -> duckdb.DuckDBPyConnection:
    """完整设置数据库（向后兼容）。"""
    return initialize_database(db_path)
