from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class XtDataClient:
    """xtquant.xtdata 轻量封装，延迟导入以便在无 QMT 环境下降级。"""

    _xtdata: Any | None = None

    @property
    def xtdata(self) -> Any:
        if self._xtdata is None:
            try:
                from minqmt.qmt_bootstrap import configure_qmt

                configure_qmt()
                from xtquant import xtdata
            except ImportError as exc:
                raise RuntimeError(
                    "未找到 xtquant。请先安装并启动 MiniQMT，"
                    "并将 QMT 安装目录下的 xtquant 包加入 PYTHONPATH。",
                ) from exc
            self._xtdata = xtdata
        return self._xtdata

    def is_connected(self) -> bool:
        """检测 MiniQMT 行情服务是否可用。"""
        try:
            xt = self.xtdata
            if hasattr(xt, "get_client"):
                client = xt.get_client()
                if client is not None and hasattr(client, "is_connected"):
                    return bool(client.is_connected())
            # 部分版本无 get_client，尝试读取交易日历来探测连通性
            if hasattr(xt, "get_trading_dates"):
                dates = xt.get_trading_dates("SH", "", "", 1)
                return bool(dates)
            return True
        except Exception:
            return False

    def get_trading_dates(
        self,
        market: str = "SH",
        start: str = "",
        end: str = "",
        count: int = -1,
    ) -> list[str]:
        xt = self.xtdata
        if hasattr(xt, "get_trading_dates"):
            return list(xt.get_trading_dates(market, start, end, count))
        return []
