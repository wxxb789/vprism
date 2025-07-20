"""数据存储仓储模式实现"""

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from vprism.core.models import MarketType, TimeFrame
from vprism.infrastructure.storage.database_schema import DatabaseSchema

logger = logging.getLogger(__name__)


class AssetInfo(BaseModel):
    """资产信息模型"""

    symbol: str
    market: str
    name: str
    asset_type: str
    currency: str
    exchange: str
    sector: str | None = None
    industry: str | None = None
    is_active: bool = True
    provider: str
    exchange_timezone: str | None = None
    first_traded: date | None = None
    last_updated: datetime | None = None
    metadata: dict[str, Any] | None = None


class OHLCVData(BaseModel):
    """OHLCV数据模型"""

    symbol: str
    market: str
    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    amount: Decimal | None = None
    adjusted_close: Decimal | None = None
    split_factor: Decimal | None = None
    dividend_amount: Decimal | None = None
    provider: str


class RealTimeQuote(BaseModel):
    """实时报价模型"""

    symbol: str
    market: str
    price: Decimal
    change_amount: Decimal | None = None
    change_percent: Decimal | None = None
    volume: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    bid_size: Decimal | None = None
    ask_size: Decimal | None = None
    timestamp: datetime
    provider: str


class DataQualityMetrics(BaseModel):
    """数据质量指标模型"""

    symbol: str
    market: str
    date_range_start: date
    date_range_end: date
    completeness_score: float
    accuracy_score: float
    consistency_score: float
    total_records: int
    missing_records: int
    anomaly_count: int
    provider: str
    checked_at: datetime


class DataRepository(ABC):
    """数据仓储抽象基类"""

    @abstractmethod
    async def save_asset_info(self, asset: AssetInfo) -> bool:
        """保存资产信息"""
        pass

    @abstractmethod
    async def get_asset_info(self, symbol: str, market: str) -> AssetInfo | None:
        """获取资产信息"""
        pass

    @abstractmethod
    async def save_ohlcv_data(self, data: list[OHLCVData]) -> bool:
        """保存OHLCV数据"""
        pass

    @abstractmethod
    async def get_ohlcv_data(
        self,
        symbol: str,
        market: str,
        start_date: date,
        end_date: date,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> list[OHLCVData]:
        """获取OHLCV数据"""
        pass

    @abstractmethod
    async def save_real_time_quote(self, quote: RealTimeQuote) -> bool:
        """保存实时报价"""
        pass

    @abstractmethod
    async def get_real_time_quote(
        self, symbol: str, market: str
    ) -> RealTimeQuote | None:
        """获取实时报价"""
        pass

    @abstractmethod
    async def save_data_quality_metrics(self, metrics: DataQualityMetrics) -> bool:
        """保存数据质量指标"""
        pass

    @abstractmethod
    async def get_data_quality_metrics(
        self, symbol: str, market: str, start_date: date, end_date: date
    ) -> DataQualityMetrics | None:
        """获取数据质量指标"""
        pass

    @abstractmethod
    async def get_symbols_by_market(self, market: MarketType) -> list[str]:
        """获取指定市场的所有股票代码"""
        pass

    @abstractmethod
    async def get_latest_price(self, symbol: str, market: str) -> Decimal | None:
        """获取最新价格"""
        pass


class DuckDBRepository(DataRepository):
    """基于DuckDB的数据仓储实现"""

    def __init__(self, db_path: str = "vprism_data.duckdb"):
        self.db_path = db_path
        self.schema = DatabaseSchema(db_path)

    async def save_asset_info(self, asset: AssetInfo) -> bool:
        """保存资产信息"""
        try:
            self.schema.conn.execute(
                """
                INSERT OR REPLACE INTO asset_info 
                (symbol, market, name, asset_type, currency, exchange, sector, 
                 industry, is_active, provider, exchange_timezone, first_traded, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    asset.symbol,
                    asset.market,
                    asset.name,
                    asset.asset_type,
                    asset.currency,
                    asset.exchange,
                    asset.sector,
                    asset.industry,
                    asset.is_active,
                    asset.provider,
                    asset.exchange_timezone,
                    asset.first_traded,
                    str(asset.metadata) if asset.metadata else None,
                ],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save asset info: {e}")
            return False

    async def get_asset_info(self, symbol: str, market: str) -> AssetInfo | None:
        """获取资产信息"""
        try:
            result = self.schema.conn.execute(
                """
                SELECT symbol, market, name, asset_type, currency, exchange, 
                       sector, industry, is_active, provider, exchange_timezone, 
                       first_traded, last_updated, metadata
                FROM asset_info 
                WHERE symbol = ? AND market = ?
            """,
                [symbol, market],
            ).fetchone()

            if result:
                return AssetInfo(
                    symbol=result[0],
                    market=result[1],
                    name=result[2],
                    asset_type=result[3],
                    currency=result[4],
                    exchange=result[5],
                    sector=result[6],
                    industry=result[7],
                    is_active=bool(result[8]),
                    provider=result[9],
                    exchange_timezone=result[10],
                    first_traded=result[11],
                    last_updated=result[12],
                    metadata=eval(result[13]) if result[13] else None,
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get asset info: {e}")
            return None

    async def save_ohlcv_data(self, data: list[OHLCVData]) -> bool:
        """保存OHLCV数据"""
        if not data:
            return True

        try:
            # 检查是否是分钟级数据（有具体时间）

            # 对于日线数据，使用时间戳的日期部分
            for item in data:
                # 检查时间戳是否有时间部分（不是00:00:00）
                has_time = (
                    item.timestamp.hour != 0
                    or item.timestamp.minute != 0
                    or item.timestamp.second != 0
                )

                if has_time:  # 分钟级数据
                    self.schema.conn.execute(
                        """
                        INSERT OR REPLACE INTO intraday_ohlcv 
                        (symbol, market, timeframe, timestamp, open_price, high_price, 
                         low_price, close_price, volume, amount, provider)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        [
                            item.symbol,
                            item.market,
                            "1m",
                            item.timestamp,
                            item.open_price,
                            item.high_price,
                            item.low_price,
                            item.close_price,
                            item.volume,
                            item.amount,
                            item.provider,
                        ],
                    )
                else:  # 日线数据
                    self.schema.conn.execute(
                        """
                        INSERT OR REPLACE INTO daily_ohlcv 
                        (symbol, market, trade_date, open_price, high_price, low_price, 
                         close_price, volume, amount, adjusted_close, provider)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        [
                            item.symbol,
                            item.market,
                            item.timestamp.date(),
                            item.open_price,
                            item.high_price,
                            item.low_price,
                            item.close_price,
                            item.volume,
                            item.amount,
                            item.adjusted_close or None,
                            item.provider,
                        ],
                    )
            return True
        except Exception as e:
            logger.error(f"Failed to save OHLCV data: {e}")
            return False

    async def get_ohlcv_data(
        self,
        symbol: str,
        market: str,
        start_date: date,
        end_date: date,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> list[OHLCVData]:
        """获取OHLCV数据"""
        try:
            # 根据时间框架选择表
            if timeframe in [
                TimeFrame.MINUTE_1,
                TimeFrame.MINUTE_5,
                TimeFrame.MINUTE_15,
                TimeFrame.MINUTE_30,
                TimeFrame.HOUR_1,
            ]:
                table_name = "intraday_ohlcv"
                time_column = "timestamp"
                start_datetime = datetime.combine(start_date, datetime.min.time())
                end_datetime = datetime.combine(
                    end_date, datetime.max.time().replace(microsecond=0)
                )
                query = f"""
                    SELECT symbol, market, timestamp, open_price, high_price, low_price, 
                           close_price, volume, amount, provider
                    FROM {table_name} 
                    WHERE symbol = ? AND market = ? AND {time_column} >= ? AND {time_column} <= ?
                    ORDER BY {time_column} ASC
                """
                params = [symbol, market, start_datetime, end_datetime]
            else:
                table_name = "daily_ohlcv"
                time_column = "trade_date"
                query = f"""
                    SELECT symbol, market, trade_date, open_price, high_price, low_price, 
                           close_price, volume, amount, adjusted_close, provider
                    FROM {table_name} 
                    WHERE symbol = ? AND market = ? AND {time_column} >= ? AND {time_column} <= ?
                    ORDER BY {time_column} ASC
                """
                params = [symbol, market, start_date, end_date]

            results = self.schema.conn.execute(query, params).fetchall()

            ohlcv_data = []
            for row in results:
                if timeframe in [
                    TimeFrame.MINUTE_1,
                    TimeFrame.MINUTE_5,
                    TimeFrame.MINUTE_15,
                    TimeFrame.MINUTE_30,
                    TimeFrame.HOUR_1,
                ]:
                    ohlcv_data.append(
                        OHLCVData(
                            symbol=row[0],
                            market=row[1],
                            timestamp=row[2],
                            open_price=Decimal(str(row[3])),
                            high_price=Decimal(str(row[4])),
                            low_price=Decimal(str(row[5])),
                            close_price=Decimal(str(row[6])),
                            volume=Decimal(str(row[7])),
                            amount=Decimal(str(row[8])) if row[8] else None,
                            provider=row[9],
                        )
                    )
                else:
                    ohlcv_data.append(
                        OHLCVData(
                            symbol=row[0],
                            market=row[1],
                            timestamp=datetime.combine(row[2], datetime.min.time()),
                            open_price=Decimal(str(row[3])),
                            high_price=Decimal(str(row[4])),
                            low_price=Decimal(str(row[5])),
                            close_price=Decimal(str(row[6])),
                            volume=Decimal(str(row[7])),
                            amount=Decimal(str(row[8])) if row[8] else None,
                            adjusted_close=Decimal(str(row[9])) if row[9] else None,
                            provider=row[10],
                        )
                    )

            return ohlcv_data
        except Exception as e:
            logger.error(f"Failed to get OHLCV data: {e}")
            return []

    async def save_real_time_quote(self, quote: RealTimeQuote) -> bool:
        """保存实时报价"""
        try:
            self.schema.conn.execute(
                """
                INSERT OR REPLACE INTO real_time_quotes 
                (symbol, market, price, change_amount, change_percent, volume, 
                 bid, ask, bid_size, ask_size, timestamp, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    quote.symbol,
                    quote.market,
                    quote.price,
                    quote.change_amount,
                    quote.change_percent,
                    quote.volume,
                    quote.bid,
                    quote.ask,
                    quote.bid_size,
                    quote.ask_size,
                    quote.timestamp,
                    quote.provider,
                ],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save real time quote: {e}")
            return False

    async def get_real_time_quote(
        self, symbol: str, market: str
    ) -> RealTimeQuote | None:
        """获取实时报价"""
        try:
            result = self.schema.conn.execute(
                """
                SELECT symbol, market, price, change_amount, change_percent, volume, 
                       bid, ask, bid_size, ask_size, timestamp, provider
                FROM real_time_quotes 
                WHERE symbol = ? AND market = ?
            """,
                [symbol, market],
            ).fetchone()

            if result:
                return RealTimeQuote(
                    symbol=result[0],
                    market=result[1],
                    price=Decimal(str(result[2])),
                    change_amount=Decimal(str(result[3])) if result[3] else None,
                    change_percent=Decimal(str(result[4])) if result[4] else None,
                    volume=Decimal(str(result[5])) if result[5] else None,
                    bid=Decimal(str(result[6])) if result[6] else None,
                    ask=Decimal(str(result[7])) if result[7] else None,
                    bid_size=Decimal(str(result[8])) if result[8] else None,
                    ask_size=Decimal(str(result[9])) if result[9] else None,
                    timestamp=result[10],
                    provider=result[11],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get real time quote: {e}")
            return None

    async def save_data_quality_metrics(self, metrics: DataQualityMetrics) -> bool:
        """保存数据质量指标"""
        try:
            self.schema.conn.execute(
                """
                INSERT OR REPLACE INTO data_quality 
                (symbol, market, date_range_start, date_range_end, completeness_score, 
                 accuracy_score, consistency_score, total_records, missing_records, 
                 anomaly_count, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    metrics.symbol,
                    metrics.market,
                    metrics.date_range_start,
                    metrics.date_range_end,
                    metrics.completeness_score,
                    metrics.accuracy_score,
                    metrics.consistency_score,
                    metrics.total_records,
                    metrics.missing_records,
                    metrics.anomaly_count,
                    metrics.provider,
                ],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save data quality metrics: {e}")
            return False

    async def get_data_quality_metrics(
        self, symbol: str, market: str, start_date: date, end_date: date
    ) -> DataQualityMetrics | None:
        """获取数据质量指标"""
        try:
            result = self.schema.conn.execute(
                """
                SELECT symbol, market, date_range_start, date_range_end, 
                       completeness_score, accuracy_score, consistency_score, 
                       total_records, missing_records, anomaly_count, provider, checked_at
                FROM data_quality 
                WHERE symbol = ? AND market = ? AND date_range_start = ? AND date_range_end = ?
            """,
                [symbol, market, start_date, end_date],
            ).fetchone()

            if result:
                return DataQualityMetrics(
                    symbol=result[0],
                    market=result[1],
                    date_range_start=result[2],
                    date_range_end=result[3],
                    completeness_score=float(result[4]),
                    accuracy_score=float(result[5]),
                    consistency_score=float(result[6]),
                    total_records=int(result[7]),
                    missing_records=int(result[8]),
                    anomaly_count=int(result[9]),
                    provider=result[10],
                    checked_at=result[11],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get data quality metrics: {e}")
            return None

    async def get_symbols_by_market(self, market: MarketType) -> list[str]:
        """获取指定市场的所有股票代码"""
        try:
            results = self.schema.conn.execute(
                """
                SELECT symbol FROM asset_info WHERE market = ? AND is_active = TRUE
            """,
                [market.value],
            ).fetchall()

            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Failed to get symbols by market: {e}")
            return []

    async def get_latest_price(self, symbol: str, market: str) -> Decimal | None:
        """获取最新价格"""
        try:
            # 先尝试从实时报价获取
            quote = await self.get_real_time_quote(symbol, market)
            if quote:
                return quote.price

            # 如果没有实时报价，从日线数据获取
            result = self.schema.conn.execute(
                """
                SELECT close_price 
                FROM daily_ohlcv 
                WHERE symbol = ? AND market = ? 
                ORDER BY trade_date DESC 
                LIMIT 1
            """,
                [symbol, market],
            ).fetchone()

            if result:
                return Decimal(str(result[0]))
            return None
        except Exception as e:
            logger.error(f"Failed to get latest price: {e}")
            return None

    def close(self):
        """关闭数据库连接"""
        self.schema.close()

    def __del__(self):
        """析构函数"""
        try:
            self.close()
        except Exception:
            pass  # 忽略析构时的错误
