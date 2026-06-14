from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Period = Literal["tick", "1m", "5m", "15m", "30m", "1h", "1d", "1w", "1mon"]
DividendType = Literal["none", "front", "back", "front_ratio", "back_ratio"]


@dataclass
class MinQmtConfig:
    """MiniQMT 数据获取默认配置。"""

    default_period: Period = "1d"
    default_dividend_type: DividendType = "front"
    fill_data: bool = True
    incremental_download: bool = True
    default_fields: list[str] = field(
        default_factory=lambda: ["open", "high", "low", "close", "volume", "amount"],
    )
