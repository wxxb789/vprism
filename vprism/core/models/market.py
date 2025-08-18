"""Market-related enums and types."""

from enum import Enum


class AssetType(str, Enum):
    """资产类型枚举."""

    STOCK = "stock"
    BOND = "bond"
    ETF = "etf"
    FUND = "fund"
    FUTURES = "futures"
    OPTIONS = "options"
    FOREX = "forex"
    CRYPTO = "crypto"
    INDEX = "index"
    COMMODITY = "commodity"
    CONVERTIBLE_BOND = "convertible_bond"


class MarketType(str, Enum):
    """市场类型枚举."""

    CN = "cn"  # 中国
    US = "us"  # 美国
    HK = "hk"  # 香港
    EU = "eu"  # 欧洲
    JP = "jp"  # 日本
    UK = "uk"  # 英国
    AU = "au"  # 澳大利亚
    GLOBAL = "global"


class TimeFrame(str, Enum):
    """时间框架枚举."""

    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"
