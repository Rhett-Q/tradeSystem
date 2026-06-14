from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable

from minqmt.client import XtDataClient
from minqmt.config import Period
from minqmt.fetcher import DownloadResult, MinQmtDataFetcher
from minqmt.symbols import normalize_symbol


@dataclass
class SyncProgress:
    phase: str
    total: int
    done: int
    failed: int
    message: str = ""

    @property
    def pct(self) -> float:
        return (self.done / self.total * 100) if self.total else 0.0


@dataclass
class SyncReport:
    mode: str
    period: str
    start_time: str
    end_time: str
    stock_count: int
    success_count: int
    failed_count: int
    started_at: str
    finished_at: str
    message: str = ""


@dataclass
class MarketDataSync:
    """
    全市场数据同步：首次全量下载 + 每日增量更新。

    典型流程::

        sync = MarketDataSync()
        sync.ensure_ready()

        # 1. 首次：近几年全市场日线
        report = sync.sync_full_market(start_time="20200101", period="1d")

        # 2. 每交易日收盘后增量
        report = sync.sync_daily_incremental(period="1d")
    """

    fetcher: MinQmtDataFetcher = field(default_factory=MinQmtDataFetcher)
    default_universe_sectors: list[str] = field(
        default_factory=lambda: ["沪深A股", "京市A股"],
    )

    def ensure_ready(self) -> None:
        self.fetcher.ensure_connected()

    def get_universe(self, sectors: Iterable[str] | None = None) -> list[str]:
        """获取全市场标的列表（裸代码）。"""
        self.ensure_ready()
        xt = self.fetcher.client.xtdata
        sectors = list(sectors or self.default_universe_sectors)
        symbols: list[str] = []

        if hasattr(xt, "download_sector_data"):
            try:
                xt.download_sector_data()
            except Exception:
                pass

        if not hasattr(xt, "get_stock_list_in_sector"):
            raise RuntimeError("当前 xtquant 不支持 get_stock_list_in_sector")

        for sector in sectors:
            raw = xt.get_stock_list_in_sector(sector) or []
            symbols.extend(normalize_symbol(c) for c in raw)

        return list(dict.fromkeys(symbols))

    def sync_full_market(
        self,
        start_time: str = "20200101",
        end_time: str = "",
        period: Period = "1d",
        *,
        batch_size: int = 200,
        sectors: Iterable[str] | None = None,
        on_progress: Callable[[SyncProgress], None] | None = None,
    ) -> SyncReport:
        """首次全量：下载全市场近几年 K 线到本地缓存。"""
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        universe = self.get_universe(sectors)
        success = 0
        failed = 0

        for i in range(0, len(universe), batch_size):
            batch = universe[i : i + batch_size]
            if on_progress:
                on_progress(
                    SyncProgress(
                        phase="full",
                        total=len(universe),
                        done=i,
                        failed=failed,
                        message=f"全量下载 batch {i // batch_size + 1}",
                    ),
                )
            results = self.fetcher.download_kline(
                batch,
                period=period,
                start_time=start_time,
                end_time=end_time,
                incrementally=False,
            )
            success += sum(1 for r in results if r.success)
            failed += sum(1 for r in results if not r.success)

        if on_progress:
            on_progress(
                SyncProgress(
                    phase="full",
                    total=len(universe),
                    done=len(universe),
                    failed=failed,
                    message="全量下载完成",
                ),
            )

        finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return SyncReport(
            mode="full",
            period=period,
            start_time=start_time,
            end_time=end_time or "today",
            stock_count=len(universe),
            success_count=success,
            failed_count=failed,
            started_at=started,
            finished_at=finished,
            message=f"全市场 {len(universe)} 只 · {start_time} 起",
        )

    def sync_daily_incremental(
        self,
        period: Period = "1d",
        *,
        sectors: Iterable[str] | None = None,
        batch_size: int = 300,
        on_progress: Callable[[SyncProgress], None] | None = None,
    ) -> SyncReport:
        """每日增量：incrementally=True，仅补最新数据。"""
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        universe = self.get_universe(sectors)
        success = 0
        failed = 0

        for i in range(0, len(universe), batch_size):
            batch = universe[i : i + batch_size]
            if on_progress:
                on_progress(
                    SyncProgress(
                        phase="incremental",
                        total=len(universe),
                        done=i,
                        failed=failed,
                        message=f"增量更新 batch {i // batch_size + 1}",
                    ),
                )
            results = self.fetcher.download_kline(
                batch,
                period=period,
                incrementally=True,
            )
            success += sum(1 for r in results if r.success)
            failed += sum(1 for r in results if not r.success)

        finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return SyncReport(
            mode="incremental",
            period=period,
            start_time="",
            end_time=datetime.now().strftime("%Y%m%d"),
            stock_count=len(universe),
            success_count=success,
            failed_count=failed,
            started_at=started,
            finished_at=finished,
            message="每日增量 · start_time 为空（从本地缓存续传）",
        )

    def download_sector_meta(self) -> None:
        """同步板块元数据（筛选依赖）。"""
        self.ensure_ready()
        xt = self.fetcher.client.xtdata
        if hasattr(xt, "download_sector_data"):
            xt.download_sector_data()
        if hasattr(xt, "download_index_weight"):
            xt.download_index_weight()
