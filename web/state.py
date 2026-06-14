from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from minqmt.pool import StockPoolBuilder
from minqmt.screener import MarketScreener, WatchItem
from minqmt.sync import MarketDataSync, SyncProgress, SyncReport

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STATE_FILE = DATA_DIR / "app_state.json"

JobStatus = Literal["idle", "running", "done", "error"]


@dataclass
class SyncJob:
    id: str
    mode: str
    status: JobStatus = "idle"
    progress: SyncProgress | None = None
    report: SyncReport | None = None
    error: str = ""


@dataclass
class AppState:
    sync: MarketDataSync = field(default_factory=MarketDataSync)
    pools: StockPoolBuilder = field(default_factory=StockPoolBuilder)
    screener: MarketScreener = field(default_factory=MarketScreener)
    watchlist: list[WatchItem] = field(default_factory=list)
    sync_job: SyncJob | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not STATE_FILE.exists():
            return
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.screener.load_custom_filters(raw.get("custom_filters", []))
            self.watchlist = [
                WatchItem(**item) for item in raw.get("watchlist", [])
            ]
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "custom_filters": self.screener.export_custom_filters(),
            "watchlist": [item.__dict__ for item in self.watchlist],
        }
        STATE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_connected(self) -> bool:
        try:
            return self.sync.fetcher.client.is_connected()
        except Exception:
            return False

    def start_sync(
        self,
        mode: Literal["full", "incremental"],
        *,
        start_time: str = "20200101",
        period: str = "1d",
        batch_size: int = 200,
    ) -> SyncJob:
        with self._lock:
            if self.sync_job and self.sync_job.status == "running":
                raise RuntimeError("已有同步任务正在运行")

            job = SyncJob(id=str(uuid.uuid4()), mode=mode, status="running")
            self.sync_job = job

        def on_progress(p: SyncProgress) -> None:
            with self._lock:
                if self.sync_job:
                    self.sync_job.progress = p

        def run() -> None:
            try:
                self.sync.ensure_ready()
                if mode == "full":
                    report = self.sync.sync_full_market(
                        start_time=start_time,
                        period=period,  # type: ignore[arg-type]
                        batch_size=batch_size,
                        on_progress=on_progress,
                    )
                else:
                    report = self.sync.sync_daily_incremental(
                        period=period,  # type: ignore[arg-type]
                        batch_size=batch_size,
                        on_progress=on_progress,
                    )
                with self._lock:
                    if self.sync_job:
                        self.sync_job.report = report
                        self.sync_job.status = "done"
            except Exception as exc:
                with self._lock:
                    if self.sync_job:
                        self.sync_job.status = "error"
                        self.sync_job.error = str(exc)

        threading.Thread(target=run, daemon=True).start()
        return job

    def add_to_watchlist(self, rows: list[dict[str, Any]]) -> list[WatchItem]:
        existing = {w.symbol for w in self.watchlist}
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for row in rows:
            sym = str(row.get("symbol", ""))
            if not sym or sym in existing:
                continue
            self.watchlist.append(
                WatchItem(
                    symbol=sym,
                    name=str(row.get("name", sym)),
                    added_at=now,
                    status="watching",
                    trigger_id="mom10",
                    trigger_progress=0.0,
                    trigger_label="等待动量突破",
                    close=float(row.get("close") or 0),
                    momentum20d=float(
                        row.get("momentum_20d") or row.get("momentum20d") or 0
                    ),
                    amount=float(row.get("amount") or 0),
                    tag_ids=list(row.get("tag_ids") or []),
                ),
            )
            existing.add(sym)
        self.save()
        return self.refresh_watchlist()

    def refresh_watchlist(self) -> list[WatchItem]:
        self.watchlist = self.screener.evaluate_triggers(self.watchlist)
        self.save()
        return self.watchlist

    def remove_watch(self, symbol: str) -> None:
        self.watchlist = [w for w in self.watchlist if w.symbol != symbol]
        self.save()
