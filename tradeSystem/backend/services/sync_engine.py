from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# 将工作区根目录加入 path，以导入 minqmt
_WORKSPACE = Path(__file__).resolve().parents[3]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from minqmt.fetcher import DownloadResult, MinQmtDataFetcher
from minqmt.sync import MarketDataSync
from minqmt.symbols import normalize_symbol, to_xt_symbol

from config.settings import get_settings
from db.repositories import kline as kline_repo
from db.repositories import sync_jobs as job_repo
from db.repositories import symbols as symbol_repo
from services.screener_filters import symbol_is_listed
from services.kline_resample import RESAMPLE_FROM_DAILY
from services.log_config import format_error
from services.time_utils import parse_bar_datetime, parse_trade_date

logger = logging.getLogger(__name__)

DAILY_PERIODS = kline_repo.DAILY_PERIODS
DB_DAILY_PERIOD = kline_repo.DB_DAILY_PERIOD
_MAX_LOG_CHARS = 4000
_PERSIST_CHUNK = 50
_INCREMENTAL_DAILY_BARS = 30
_INCREMENTAL_INTRADAY_BARS = 20


class SyncEngine:
    """MiniQMT 下载 + PostgreSQL 持久化。"""

    def __init__(self) -> None:
        self._sync = MarketDataSync()
        self._lock = threading.Lock()
        self._cancel_flags: dict[str, bool] = {}

    @property
    def fetcher(self) -> MinQmtDataFetcher:
        return self._sync.fetcher

    def is_minqmt_connected(self) -> bool:
        try:
            return self._sync.fetcher.client.is_connected()
        except Exception as exc:
            logger.warning("MiniQMT 连接检测失败: %s", exc)
            return False

    def get_universe_count(self) -> int:
        self._sync.ensure_ready()
        return len(self._sync.get_universe())

    def start_job(
        self,
        mode: str,
        period: str = "1d",
        start_date: str = "20200101",
        batch_size: int | None = None,
    ) -> str:
        if period in RESAMPLE_FROM_DAILY:
            label = "周线" if period == "1w" else "月线"
            raise RuntimeError(
                f"{label}（{period}）由日 K 重采样生成，请同步日线 1d；K 线页选择周线即可查看",
            )
        if job_repo.has_running_job():
            raise RuntimeError("已有同步任务正在运行")

        settings = get_settings()
        batch_size = batch_size or settings.sync_batch_size
        job_id = job_repo.create_job(
            job_type=mode,
            period=period,
            start_date=start_date if mode == "full" else None,
            batch_size=batch_size,
        )
        self._cancel_flags[job_id] = False

        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, mode, period, start_date, batch_size),
            daemon=True,
            name=f"sync-{job_id[:8]}",
        )
        thread.start()
        logger.info("同步任务已启动 job_id=%s mode=%s period=%s", job_id, mode, period)
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        self._cancel_flags[job_id] = True
        return job_repo.cancel_job(job_id)

    def _is_cancelled(self, job_id: str) -> bool:
        return self._cancel_flags.get(job_id, False)

    def _log(self, job_id: str, level: str, message: str, symbol: str | None = None) -> None:
        text = message[:_MAX_LOG_CHARS]
        try:
            job_repo.add_log(job_id, level, text, symbol)
        except Exception as exc:
            logger.error("写入 sync_logs 失败 job=%s: %s", job_id, exc)
        log_fn = {
            "error": logger.error,
            "warn": logger.warning,
            "warning": logger.warning,
        }.get(level, logger.info)
        prefix = f"[{job_id[:8]}]"
        if symbol:
            prefix += f" [{symbol}]"
        log_fn("%s %s", prefix, text.replace("\n", " | "))

    def _log_exception(self, job_id: str, message: str, exc: BaseException, symbol: str | None = None) -> None:
        detail = format_error(message, exc)
        self._log(job_id, "error", detail, symbol)

    def _run_job(
        self,
        job_id: str,
        mode: str,
        period: str,
        start_date: str,
        batch_size: int,
    ) -> None:
        try:
            self._log(job_id, "info", f"任务开始 mode={mode} period={period} batch={batch_size}")
            self._sync.ensure_ready()
            universe_xt = self._sync.get_universe()
            job_repo.update_job_running(job_id, len(universe_xt))
            self._log(job_id, "info", f"获取标的 {len(universe_xt)} 只 · 批大小 {batch_size}")

            self._sync_symbols(job_id, universe_xt, batch_size)

            if self._is_cancelled(job_id):
                return

            done = 0
            failed = 0
            empty_batches = 0
            total_persisted = 0

            for i in range(0, len(universe_xt), batch_size):
                if self._is_cancelled(job_id):
                    job_repo.finish_job(job_id, "cancelled", "任务已取消", done)
                    self._log(job_id, "warn", "任务被用户取消")
                    return

                batch = universe_xt[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(universe_xt) + batch_size - 1) // batch_size
                self._log(job_id, "info", f"批次 {batch_num}/{total_batches} · 下载 {len(batch)} 只 · 示例 {batch[0]}")
                job_repo.update_job_progress(
                    job_id,
                    done,
                    max(1, int(done / len(universe_xt) * 100)) if done else 1,
                    f"批次 {batch_num}/{total_batches} · 准备下载…",
                )

                def on_download_progress(data: dict) -> None:
                    fin = data.get("finished") or 0
                    total = data.get("total") or len(batch)
                    if not total:
                        return
                    in_batch = min(int(fin), len(batch))
                    overall_done = done + in_batch
                    pct = max(1, int(overall_done / len(universe_xt) * 100))
                    phase = data.get("phase", "target")
                    if phase == "base":
                        step = f"批次 {batch_num}/{total_batches} · 日线 1d {fin}/{total}"
                    else:
                        step = f"批次 {batch_num}/{total_batches} · 下载 {fin}/{total}"
                    job_repo.update_job_progress(
                        job_id,
                        overall_done,
                        pct,
                        step,
                    )

                try:
                    if mode == "full":
                        results = self._sync.fetcher.download_kline(
                            batch,
                            period=period,  # type: ignore[arg-type]
                            start_time=start_date,
                            incrementally=False,
                            on_progress=on_download_progress,
                        )
                    else:
                        results = self._sync.fetcher.download_kline(
                            batch,
                            period=period,  # type: ignore[arg-type]
                            incrementally=True,
                            on_progress=on_download_progress,
                        )

                    batch_failed = self._log_download_results(job_id, results)
                    failed += batch_failed

                    if batch_failed < len(batch):
                        job_repo.update_job_progress(
                            job_id,
                            done,
                            max(1, int(done / len(universe_xt) * 100)) if done else 1,
                            f"批次 {batch_num}/{total_batches} · 写入 PostgreSQL…",
                        )
                        persisted = self._persist_batch(
                            job_id,
                            batch,
                            period,
                            mode,
                            start_date if mode == "full" else "",
                            batch_num=batch_num,
                            total_batches=total_batches,
                            symbols_done=done,
                            symbols_total=len(universe_xt),
                        )
                    else:
                        persisted = 0
                        self._log(
                            job_id,
                            "warn",
                            f"批次 {batch_num} 全部下载失败，跳过写入（period={period}）",
                        )
                    total_persisted += persisted
                    if persisted == 0:
                        empty_batches += 1
                        sample = ", ".join(normalize_symbol(c) for c in batch[:5])
                        self._log(
                            job_id,
                            "warn",
                            f"批次 {batch_num} 下载完成但写入 0 条（{len(batch)} 只），示例: {sample}。"
                            " 若持续出现请确认 MiniQMT 已登录且行情服务正常",
                        )

                    done += len(batch)
                    progress = int(done / len(universe_xt) * 100)
                    job_repo.update_job_progress(
                        job_id,
                        done,
                        progress,
                        f"已处理 {done}/{len(universe_xt)} · 本批写入 {persisted} 条 · 累计 {total_persisted} 条",
                    )
                except Exception as exc:
                    failed += len(batch)
                    done += len(batch)
                    sample = ", ".join(normalize_symbol(c) for c in batch[:5])
                    self._log_exception(
                        job_id,
                        f"批次 {batch_num} 异常（{len(batch)} 只，示例 {sample}）",
                        exc,
                    )

            success_count = done - failed
            if failed >= len(universe_xt) or (total_persisted == 0 and done > 0):
                status = "failed"
            elif failed > 0 or empty_batches > 0:
                status = "completed"
            else:
                status = "completed"

            summary = (
                f"完成 {success_count}/{len(universe_xt)} 只下载成功，"
                f"失败 {failed}，空批次 {empty_batches}，共写入 {total_persisted} 条 K 线"
            )
            if status == "failed":
                summary = f"任务失败: {summary}"
            job_repo.finish_job(job_id, status, summary, done)
            self._log(job_id, "error" if status == "failed" else "info", summary)

        except Exception as exc:
            self._log_exception(job_id, "任务整体失败", exc)
            job_repo.finish_job(job_id, "failed", str(exc))
        finally:
            self._cancel_flags.pop(job_id, None)
            logger.info("同步任务结束 job_id=%s", job_id)

    def _log_download_results(self, job_id: str, results: list[DownloadResult]) -> int:
        failed = sum(1 for r in results if not r.success)
        if failed:
            for r in results:
                if not r.success:
                    sym = normalize_symbol(r.stock_code)
                    msg = r.message or "download 未成功"
                    self._log(job_id, "error", f"下载失败 period={r.period} start={r.start_time}: {msg}", sym)
            self._log(job_id, "warn", f"本批次 {len(results)} 只中有 {failed} 只下载失败")
        return failed

    def _build_symbol_rows(
        self,
        universe_xt: list[str],
        batch_size: int,
        *,
        refresh_sectors: bool = False,
    ) -> list[tuple[str, str, str | None, bool]]:
        bare_codes = [normalize_symbol(c) for c in universe_xt]
        name_map = self._sync.fetcher.get_instrument_names(bare_codes, batch_size=batch_size)
        details_map = self._sync.fetcher.get_instrument_details_map(bare_codes, batch_size=batch_size)
        industry_map = self._sync.fetcher.get_sw1_industry_map(force_refresh=refresh_sectors)
        rows: list[tuple[str, str, str | None, bool]] = []
        for bare in bare_codes:
            detail = details_map.get(bare, {})
            name = name_map.get(bare) or self._sync.fetcher._detail_to_name(detail)
            is_listed = symbol_is_listed(name, detail)
            rows.append((to_xt_symbol(bare), name, industry_map.get(bare), is_listed))
        return rows

    def _sync_symbols(self, job_id: str, universe_xt: list[str], batch_size: int) -> None:
        """写入标的元数据（含中文名称与申万一级行业）。"""
        self._log(job_id, "info", f"正在获取 {len(universe_xt)} 只标的名称与板块…")
        rows = self._build_symbol_rows(universe_xt, batch_size)
        for i in range(0, len(rows), batch_size):
            symbol_repo.upsert_symbols_batch(rows[i : i + batch_size])
        named = sum(1 for _, name, _, _ in rows if name)
        sectored = sum(1 for _, _, sector, _ in rows if sector)
        listed = sum(1 for *_, is_listed in rows if is_listed)
        self._log(
            job_id,
            "info",
            f"标的元数据已写入 {len(rows)} 只（{named} 只有名称，{sectored} 只有板块，{listed} 只正常交易）",
        )

    def _persist_read_params(self, mode: str, period: str, start_time: str) -> tuple[int, str]:
        """增量同步只读最近 K 线，避免 count=-1 拉全历史导致卡住。"""
        if mode != "incremental":
            return -1, start_time
        if period in DB_DAILY_PERIOD:
            recent_start = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
            return _INCREMENTAL_DAILY_BARS, recent_start
        return _INCREMENTAL_INTRADAY_BARS, ""

    def _persist_batch(
        self,
        job_id: str,
        batch: list[str],
        period: str,
        mode: str,
        start_time: str = "",
        *,
        batch_num: int = 1,
        total_batches: int = 1,
        symbols_done: int = 0,
        symbols_total: int = 0,
    ) -> int:
        end_time = datetime.now().strftime("%Y%m%d")
        count, eff_start = self._persist_read_params(mode, period, start_time)
        total_persisted = 0

        for offset in range(0, len(batch), _PERSIST_CHUNK):
            sub = batch[offset : offset + _PERSIST_CHUNK]
            sub_end = min(offset + len(sub), len(batch))
            if symbols_total:
                step = f"批次 {batch_num}/{total_batches} · 写入 {sub_end}/{len(batch)} 只"
                pct = max(1, int((symbols_done + sub_end) / symbols_total * 100))
                job_repo.update_job_progress(job_id, symbols_done + sub_end, pct, step)

            bare_codes = [normalize_symbol(c) for c in sub]
            try:
                df = self._sync.fetcher.get_kline(
                    bare_codes,
                    period=period,  # type: ignore[arg-type]
                    start_time=eff_start or "",
                    end_time=end_time,
                    count=count,
                )
            except Exception as exc:
                self._log_exception(job_id, f"读取 K 线缓存失败（{len(sub)} 只）", exc)
                raise

            if df.empty:
                continue

            if eff_start and "time" in df.columns:
                start_d = parse_trade_date(eff_start)
                df = df[df["time"].apply(lambda t: parse_trade_date(t) >= start_d)]
                if df.empty:
                    continue

            try:
                if period in DB_DAILY_PERIOD:
                    total_persisted += self._df_to_daily(df)
                else:
                    total_persisted += self._df_to_intraday(df, period)
            except Exception as exc:
                self._log_exception(job_id, f"写入 PostgreSQL 失败（{len(sub)} 只）", exc)
                raise

        if total_persisted:
            self._log(job_id, "info", f"批次 {batch_num} 写入 {total_persisted} 条")
        return total_persisted

    def _df_to_daily(self, df: pd.DataFrame) -> int:
        rows: list[tuple] = []
        for _, row in df.iterrows():
            close = float(row.get("close", 0) or 0)
            if close != close or close <= 0:
                continue
            sym = to_xt_symbol(str(row["symbol"]))
            trade_date = parse_trade_date(row["time"])
            rows.append(
                (
                    sym,
                    trade_date,
                    float(row.get("open", 0)),
                    float(row.get("high", 0)),
                    float(row.get("low", 0)),
                    close,
                    int(row.get("volume", 0) or 0),
                    float(row.get("amount", 0) or 0),
                ),
            )
        return kline_repo.upsert_daily_rows(rows)

    def _df_to_intraday(self, df: pd.DataFrame, period: str) -> int:
        rows: list[tuple] = []
        for _, row in df.iterrows():
            close = float(row.get("close", 0) or 0)
            if close != close or close <= 0:
                continue
            sym = to_xt_symbol(str(row["symbol"]))
            bar_time = parse_bar_datetime(row["time"])
            rows.append(
                (
                    sym,
                    period,
                    bar_time,
                    float(row.get("open", 0)),
                    float(row.get("high", 0)),
                    float(row.get("low", 0)),
                    float(row.get("close", 0)),
                    int(row.get("volume", 0) or 0),
                    float(row.get("amount", 0) or 0),
                ),
            )
        return kline_repo.upsert_intraday_rows(rows)

    def refresh_universe_to_db(self) -> int:
        settings = get_settings()
        self._sync.ensure_ready()
        universe = self._sync.get_universe()
        xt_symbols = [to_xt_symbol(s) for s in universe]
        rows = self._build_symbol_rows(universe, settings.sync_batch_size, refresh_sectors=True)
        batch_size = settings.sync_batch_size
        for i in range(0, len(rows), batch_size):
            symbol_repo.upsert_symbols_batch(rows[i : i + batch_size])
        delisted = symbol_repo.mark_unlisted_except(xt_symbols)
        if delisted:
            logger.info("标记退市标的 %s 只", delisted)
        return len(universe)


_engine: SyncEngine | None = None


def get_sync_engine() -> SyncEngine:
    global _engine
    if _engine is None:
        _engine = SyncEngine()
    return _engine
