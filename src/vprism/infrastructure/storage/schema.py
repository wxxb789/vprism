"""数据库表结构和初始化."""

import duckdb
from typing import Optional
import os


def initialize_database(db_path: str = "data/vprism.db") -> duckdb.DuckDBPyConnection:
    """初始化数据库表结构."""
    
    # 确保数据目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 连接数据库
    conn = duckdb.connect(db_path)
    
    # 创建数据记录表
    conn.execute("""
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
    
    # 创建提供商记录表
    conn.execute("""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            capabilities JSON
        )
    """)
    
    # 创建缓存记录表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_records (
            id VARCHAR PRIMARY KEY,
            cache_key VARCHAR NOT NULL,
            query_hash VARCHAR NOT NULL,
            data_source VARCHAR,
            hit_count BIGINT DEFAULT 0,
            last_access TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            metadata JSON
        )
    """)
    
    # 创建查询记录表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_records (
            id VARCHAR PRIMARY KEY,
            query_hash VARCHAR NOT NULL,
            asset_type VARCHAR NOT NULL,
            market VARCHAR,
            symbols VARCHAR[],
            timeframe VARCHAR,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            provider VARCHAR,
            status VARCHAR DEFAULT 'pending',
            request_time_ms BIGINT,
            response_size BIGINT,
            cache_hit BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    # 创建索引以提高查询性能
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_symbol ON data_records(symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_timestamp ON data_records(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_asset_market ON data_records(asset_type, market)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_provider ON data_records(provider)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_timeframe ON data_records(timeframe)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_key ON cache_records(cache_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_records(expires_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_query_hash ON query_records(query_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_query_created ON query_records(created_at)")
    
    # 创建分区表（按月份分区数据记录）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS data_records_partitioned (
            id VARCHAR,
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
            metadata JSON,
            year INTEGER,
            month INTEGER
        )
    """)
    
    # 创建分区表索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_partitioned_symbol ON data_records_partitioned(symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_partitioned_timestamp ON data_records_partitioned(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_partitioned_year_month ON data_records_partitioned(year, month)")
    
    return conn


def create_views(conn: duckdb.DuckDBPyConnection) -> None:
    """创建数据库视图."""
    
    # 创建数据汇总视图
    conn.execute("""
        CREATE OR REPLACE VIEW data_summary AS
        SELECT 
            symbol,
            asset_type,
            market,
            timeframe,
            provider,
            COUNT(*) as record_count,
            MIN(timestamp) as earliest_date,
            MAX(timestamp) as latest_date,
            AVG(close) as avg_close,
            MIN(close) as min_close,
            MAX(close) as max_close,
            SUM(volume) as total_volume
        FROM data_records
        GROUP BY symbol, asset_type, market, timeframe, provider
    """)
    
    # 创建缓存统计视图
    conn.execute("""
        CREATE OR REPLACE VIEW cache_statistics AS
        SELECT 
            data_source,
            COUNT(*) as total_entries,
            SUM(hit_count) as total_hits,
            AVG(hit_count) as avg_hits_per_entry,
            COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 END) as active_entries,
            COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 END) as expired_entries
        FROM cache_records
        GROUP BY data_source
    """)
    
    # 创建提供商性能视图
    conn.execute("""
        CREATE OR REPLACE VIEW provider_performance AS
        SELECT 
            name,
            status,
            request_count,
            error_count,
            CASE 
                WHEN request_count > 0 
                THEN CAST(error_count AS DOUBLE) / request_count * 100 
                ELSE 0 
            END as error_rate,
            avg_response_time_ms,
            last_healthy,
            updated_at
        FROM provider_records
    """)


def setup_database(db_path: str = "data/vprism.db") -> duckdb.DuckDBPyConnection:
    """完整设置数据库."""
    conn = initialize_database(db_path)
    create_views(conn)
    return conn