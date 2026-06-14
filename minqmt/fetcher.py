from __future__ import annotations

import inspect
import logging
import re
import threading
import time
from concurrent import futures
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable

import pandas as pd

from minqmt.client import XtDataClient
from minqmt.config import DividendType, MinQmtConfig, Period
from minqmt.symbols import normalize_symbol, to_xt_symbol, to_xt_symbols

logger = logging.getLogger(__name__)

_STOCK_CODE_RE = re.compile(r"\d{6}\.(SH|SZ|BJ)", re.IGNORECASE)


def _fn_supports_incrementally(fn: Any) -> bool:
    try:
        return "incrementally" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _resolve_download_times(
    start_time: str,
    end_time: str,
    incrementally: bool,
    *,
    supports_incrementally: bool,
) -> tuple[str, str, dict[str, Any]]:
    """
    Map incrementally flag to xtquant download args.

    Newer xtquant exposes incrementally=...; older builds use empty start_time
    for incremental updates from local cache.
    """
    extra: dict[str, Any] = {}
    eff_start = start_time
    eff_end = end_time

    if supports_incrementally:
        extra["incrementally"] = incrementally
    elif incrementally:
        eff_start = ""

    return eff_start, eff_end, extra


def _callback_stock_code(data: dict[str, Any]) -> str:
    """从 download_history_data2 回调中提取并规范化为 xt 代码。"""
    for key in ("stockcode", "stock_code", "stockCode", "code"):
        raw = data.get(key)
        if raw:
            return to_xt_symbol(normalize_symbol(str(raw)))
    # 部分 xtquant 版本把当前完成的代码放在 message 字段
    for key in ("message", "msg"):
        val = str(data.get(key) or "")
        match = _STOCK_CODE_RE.search(val)
        if match:
            return to_xt_symbol(normalize_symbol(match.group(0)))
    return ""


def _callback_message(data: dict[str, Any]) -> str:
    for key in ("message", "error", "msg", "errmsg"):
        val = data.get(key)
        if val and not _STOCK_CODE_RE.fullmatch(str(val).strip()):
            return str(val)
    return ""


def _batch_is_complete(data: dict[str, Any]) -> bool:
    total = data.get("total")
    fin = data.get("finished")
    return isinstance(total, int) and isinstance(fin, int) and total > 0 and fin >= total


_SLOW_DOWNLOAD_TIMEOUT = 45


def _call_xt_with_timeout(fn: Any, *args: Any, timeout: int = _SLOW_DOWNLOAD_TIMEOUT, **kwargs: Any) -> None:
    with futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
        future.result(timeout=timeout)


def _wrap_progress_phase(
    on_progress: Callable[[dict[str, Any]], None] | None,
    phase: str,
) -> Callable[[dict[str, Any]], None] | None:
    if not on_progress:
        return None

    def wrapped(data: dict[str, Any]) -> None:
        on_progress({**data, "phase": phase})

    return wrapped


_SLOW_BATCH_PERIODS = frozenset({"1w", "1mon"})
# 合成周期依赖的基础周期（QMT 内部由日线合成周线/月线）
_SYNTH_PERIOD_BASE: dict[str, Period] = {"1w": "1d", "1mon": "1d"}


@dataclass
class DownloadResult:
    stock_code: str
    period: str
    start_time: str
    end_time: str
    success: bool
    message: str = ""


@dataclass
class MinQmtDataFetcher:
    """
    MiniQMT 数据获取器。

    典型用法::

        fetcher = MinQmtDataFetcher()
        fetcher.ensure_connected()

        # 1. 下载到本地缓存
        fetcher.download_kline(["600519", "000001"], period="1d", start_time="20240101")

        # 2. 从缓存读取
        df = fetcher.get_kline(["600519"], period="1d", count=120)

        # 3. 实时快照
        ticks = fetcher.get_full_tick(["600519.SH"])
    """

    config: MinQmtConfig = field(default_factory=MinQmtConfig)
    client: XtDataClient = field(default_factory=XtDataClient)
    _sw1_industry_cache: dict[str, str] | None = field(default=None, init=False, repr=False)

    def ensure_connected(self) -> None:
        if not self.client.is_connected():
            raise ConnectionError(
                "MiniQMT 未连接。请确认 MiniQMT 客户端已登录并保持运行。",
            )

    def _kline_cached(self, code: str, period: Period) -> bool:
        """检查本地缓存是否已有 K 线（不用 start_time 过滤）。"""
        try:
            bare = normalize_symbol(code)
            if period in _SLOW_BATCH_PERIODS:
                df = self._fetch_local_df([bare], period, count=5)
            else:
                df = self.get_kline([bare], period=period, count=5)
            return not df.empty
        except Exception:
            return False

    def _fetch_local_df(
        self,
        symbols: list[str],
        period: Period,
        *,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        fields: list[str] | None = None,
        dividend_type: DividendType | None = None,
    ) -> pd.DataFrame:
        xt = self.client.xtdata
        fields = fields or self.config.default_fields
        dividend_type = dividend_type or self.config.default_dividend_type
        xt_symbols = to_xt_symbols(symbols)
        if not hasattr(xt, "get_local_data"):
            return pd.DataFrame()
        try:
            local = xt.get_local_data(
                field_list=fields,
                stock_list=xt_symbols,
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count if count > 0 else -1,
                dividend_type=dividend_type,
                fill_data=self.config.fill_data,
            )
        except Exception as exc:
            logger.debug("get_local_data 失败 period=%s: %s", period, exc)
            return pd.DataFrame()
        if local is None:
            return pd.DataFrame()
        return self._market_data_to_df(local, xt_symbols, fields)

    def _fetch_market_df(
        self,
        symbols: list[str],
        period: Period,
        *,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        fields: list[str] | None = None,
        dividend_type: DividendType | None = None,
    ) -> pd.DataFrame:
        xt = self.client.xtdata
        fields = fields or self.config.default_fields
        dividend_type = dividend_type or self.config.default_dividend_type
        xt_symbols = to_xt_symbols(symbols)
        try:
            if hasattr(xt, "get_market_data_ex"):
                raw = xt.get_market_data_ex(
                    field_list=fields,
                    stock_list=xt_symbols,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    count=count,
                    dividend_type=dividend_type,
                    fill_data=self.config.fill_data,
                )
            else:
                raw = xt.get_market_data(
                    field_list=fields,
                    stock_list=xt_symbols,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    count=count,
                    dividend_type=dividend_type,
                    fill_data=self.config.fill_data,
                )
        except Exception as exc:
            logger.debug("get_market_data 失败 period=%s: %s", period, exc)
            return pd.DataFrame()
        if raw is None:
            return pd.DataFrame()
        return self._market_data_to_df(raw, xt_symbols, fields)

    def _download_single(
        self,
        code: str,
        period: Period,
        start_time: str,
        end_time: str,
        incrementally: bool,
    ) -> DownloadResult:
        xt = self.client.xtdata
        if not hasattr(xt, "download_history_data"):
            return DownloadResult(
                code, period, start_time, end_time, False, "不支持 download_history_data",
            )
        fn = xt.download_history_data
        supports_inc = _fn_supports_incrementally(fn)
        eff_start, eff_end, extra = _resolve_download_times(
            start_time,
            end_time,
            incrementally,
            supports_incrementally=supports_inc,
        )
        try:
            if period in _SLOW_BATCH_PERIODS:
                _call_xt_with_timeout(
                    fn, code, period, start_time=eff_start, end_time=eff_end, **extra,
                )
            else:
                fn(code, period, start_time=eff_start, end_time=eff_end, **extra)
        except futures.TimeoutError:
            return DownloadResult(
                code, period, start_time, end_time, False, f"download 超时（>{_SLOW_DOWNLOAD_TIMEOUT}s）",
            )
        except Exception as exc:
            return DownloadResult(code, period, start_time, end_time, False, str(exc))

        wait = 0.2 if period in _SLOW_BATCH_PERIODS else 0.05
        attempts = 6 if period in _SLOW_BATCH_PERIODS else 1
        for _ in range(attempts):
            time.sleep(wait)
            if self._kline_cached(code, period):
                return DownloadResult(code, period, start_time, end_time, True)

        return DownloadResult(
            code,
            period,
            start_time,
            end_time,
            False,
            "download_history_data 已调用但本地无 K 线数据",
        )

    def _download_sequential(
        self,
        symbols: list[str],
        period: Period,
        start_time: str,
        end_time: str,
        incrementally: bool,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[DownloadResult]:
        """逐只下载（用于周线/月线等 batch API 不可靠的周期）。"""
        results: list[DownloadResult] = []
        total = len(symbols)
        for idx, code in enumerate(symbols, start=1):
            results.append(
                self._download_single(code, period, start_time, end_time, incrementally),
            )
            if on_progress:
                on_progress({"finished": idx, "total": total, "message": code, "phase": "target"})
        return results

    # ── 下载 ────────────────────────────────────────────────────────────────

    def download_kline(
        self,
        stock_list: Iterable[str],
        period: Period | None = None,
        start_time: str = "",
        end_time: str = "",
        incrementally: bool | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        *,
        ensure_base: bool = True,
    ) -> list[DownloadResult]:
        """批量下载 K 线到本地缓存（合成周期会先补全基础周期日线）。"""
        self.ensure_connected()
        period = period or self.config.default_period
        symbols = to_xt_symbols(list(stock_list))
        incrementally = (
            self.config.incremental_download if incrementally is None else incrementally
        )

        if ensure_base and period in _SYNTH_PERIOD_BASE:
            base_period = _SYNTH_PERIOD_BASE[period]
            logger.info(
                "合成周期 %s：先下载基础周期 %s（%d 只，start=%s）",
                period,
                base_period,
                len(symbols),
                start_time or "增量",
            )
            base_results = self.download_kline(
                symbols,
                period=base_period,
                start_time=start_time,
                end_time=end_time,
                incrementally=incrementally,
                on_progress=_wrap_progress_phase(on_progress, "base"),
                ensure_base=False,
            )
            base_failed = sum(1 for r in base_results if not r.success)
            if base_failed:
                logger.warning(
                    "基础周期 %s 下载失败 %d/%d 只，合成周期 %s 可能仍无数据",
                    base_period,
                    base_failed,
                    len(base_results),
                    period,
                )

        return self._download_kline_impl(
            symbols,
            period,  # type: ignore[arg-type]
            start_time,
            end_time,
            incrementally,
            on_progress,
        )

    def _download_kline_impl(
        self,
        symbols: list[str],
        period: Period,
        start_time: str,
        end_time: str,
        incrementally: bool,
        on_progress: Callable[[dict[str, Any]], None] | None,
    ) -> list[DownloadResult]:
        xt = self.client.xtdata
        results: list[DownloadResult] = []

        progress_cb = _wrap_progress_phase(on_progress, "target")

        if len(symbols) == 1:
            results.append(
                self._download_single(
                    symbols[0],
                    period,
                    start_time,
                    end_time,
                    incrementally,
                ),
            )
            return results

        if not hasattr(xt, "download_history_data2"):
            return self._download_sequential(
                symbols,
                period,
                start_time,
                end_time,
                incrementally,
                progress_cb,
            )

        finished: dict[str, str] = {}
        lock = threading.Lock()
        done_event = threading.Event()
        last_callback: dict[str, Any] = {}
        batch_complete = False

        def _callback(data: dict[str, Any]) -> None:
            nonlocal last_callback, batch_complete
            last_callback = data
            if progress_cb:
                progress_cb(data)
            code = _callback_stock_code(data)
            msg = _callback_message(data)
            if code:
                with lock:
                    finished[code] = msg
            if _batch_is_complete(data):
                batch_complete = True
                done_event.set()

        fn2 = xt.download_history_data2
        supports_inc = _fn_supports_incrementally(fn2)
        eff_start, eff_end, extra = _resolve_download_times(
            start_time,
            end_time,
            incrementally,
            supports_incrementally=supports_inc,
        )
        try:
            fn2(
                symbols,
                period,
                start_time=eff_start,
                end_time=eff_end,
                callback=_callback,
                **extra,
            )
        except Exception as exc:
            logger.exception("download_history_data2 调用异常")
            for code in symbols:
                results.append(
                    DownloadResult(code, period, start_time, end_time, False, str(exc)),
                )
            return results

        wait_sec = max(20, min(len(symbols) * 2, 90 if period in _SLOW_BATCH_PERIODS else 120))
        if not batch_complete:
            done_event.wait(timeout=wait_sec)
            deadline = time.time() + wait_sec
            while not batch_complete and time.time() < deadline:
                time.sleep(0.2)

        if batch_complete:
            time.sleep(0.5)
            logger.info(
                "download_history_data2 批量完成 %s/%s，回调记录 %d 只",
                last_callback.get("finished"),
                last_callback.get("total"),
                len(finished),
            )
            for code in symbols:
                results.append(
                    DownloadResult(code, period, start_time, end_time, True, "批量下载完成"),
                )
            return results

        logger.warning(
            "download_history_data2 未完成 batch_complete，回调 %d/%d，最后: %s",
            len(finished),
            len(symbols),
            last_callback,
        )
        for code in symbols:
            msg = finished.get(code, "")
            ok = code in finished or self._kline_cached(code, period)  # type: ignore[arg-type]
            if not ok and period not in _SLOW_BATCH_PERIODS:
                single = self._download_single(
                    code,
                    period,  # type: ignore[arg-type]
                    start_time,
                    end_time,
                    incrementally,
                )
                ok = single.success
                msg = single.message or msg
            if not ok and last_callback:
                msg = (msg or "下载未完成") + f"；最后回调={last_callback}"
            results.append(
                DownloadResult(code, period, start_time, end_time, ok, msg),
            )
        return results

    def download_financial(
        self,
        stock_list: Iterable[str],
        table_list: list[str] | None = None,
        start_time: str = "",
        end_time: str = "",
    ) -> None:
        """下载财务数据到本地缓存。"""
        self.ensure_connected()
        xt = self.client.xtdata
        symbols = to_xt_symbols(list(stock_list))
        tables = table_list or ["Balance", "Income", "CashFlow"]

        if hasattr(xt, "download_financial_data2"):
            xt.download_financial_data2(symbols, tables, start_time, end_time)
        elif hasattr(xt, "download_financial_data"):
            for code in symbols:
                xt.download_financial_data(code, tables, start_time, end_time)
        else:
            raise RuntimeError("当前 xtquant 版本不支持财务数据下载")

    # ── 读取 ────────────────────────────────────────────────────────────────

    def get_kline(
        self,
        stock_list: Iterable[str],
        period: Period | None = None,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        fields: list[str] | None = None,
        dividend_type: DividendType | None = None,
    ) -> pd.DataFrame:
        """
        从本地缓存读取 K 线，返回 long-format DataFrame。

        列: symbol, time, open, high, low, close, volume, amount, ...
        """
        self.ensure_connected()
        period = period or self.config.default_period
        fields = fields or self.config.default_fields
        dividend_type = dividend_type or self.config.default_dividend_type
        symbols = to_xt_symbols(list(stock_list))

        read_kwargs = {
            "start_time": start_time,
            "end_time": end_time,
            "count": count,
            "fields": fields,
            "dividend_type": dividend_type,
        }

        # 周线/月线：优先读本地文件，get_market_data_ex 对非日线常返回 None
        if period in _SLOW_BATCH_PERIODS:
            df = self._fetch_local_df(symbols, period, **read_kwargs)
            if not df.empty:
                return df
            df = self._fetch_market_df(symbols, period, **read_kwargs)
            return df

        df = self._fetch_market_df(symbols, period, **read_kwargs)
        if not df.empty:
            return df
        return self._fetch_local_df(symbols, period, **read_kwargs)

    def get_full_tick(self, stock_list: Iterable[str]) -> dict[str, dict[str, Any]]:
        """获取最新 tick 快照。"""
        self.ensure_connected()
        xt = self.client.xtdata
        symbols = to_xt_symbols(list(stock_list))
        if not hasattr(xt, "get_full_tick"):
            raise RuntimeError("当前 xtquant 版本不支持 get_full_tick")
        return xt.get_full_tick(symbols)

    def get_instrument_detail(self, stock_code: str) -> dict[str, Any]:
        """获取合约基础信息（名称、上市日等）。"""
        self.ensure_connected()
        xt = self.client.xtdata
        symbol = to_xt_symbol(stock_code)
        if hasattr(xt, "get_instrument_detail"):
            return dict(xt.get_instrument_detail(symbol) or {})
        return {}

    @staticmethod
    def _detail_to_name(detail: dict[str, Any] | None) -> str:
        if not detail:
            return ""
        return str(detail.get("InstrumentName") or detail.get("name") or "").strip()

    def get_instrument_names(self, stock_codes: list[str], *, batch_size: int = 500) -> dict[str, str]:
        """批量获取中文名称，返回 {裸代码: 名称}。"""
        if not stock_codes:
            return {}

        self.ensure_connected()
        xt = self.client.xtdata
        bare_codes = [normalize_symbol(c) for c in stock_codes]
        names: dict[str, str] = {}

        if hasattr(xt, "get_instrument_detail_list"):
            symbols = to_xt_symbols(bare_codes)
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i : i + batch_size]
                try:
                    details = xt.get_instrument_detail_list(batch) or {}
                except Exception as exc:
                    logger.warning("get_instrument_detail_list 批次失败: %s", exc)
                    details = {}
                for sym, detail in details.items():
                    name = self._detail_to_name(detail if isinstance(detail, dict) else None)
                    if name:
                        names[normalize_symbol(sym)] = name
            return names

        for bare in bare_codes:
            name = self._detail_to_name(self.get_instrument_detail(bare))
            if name:
                names[bare] = name
        return names

    def get_instrument_details_map(
        self,
        stock_codes: list[str],
        *,
        batch_size: int = 500,
    ) -> dict[str, dict[str, Any]]:
        """批量获取合约详情，返回 {裸代码: detail}。"""
        if not stock_codes:
            return {}

        self.ensure_connected()
        xt = self.client.xtdata
        bare_codes = [normalize_symbol(c) for c in stock_codes]
        details_map: dict[str, dict[str, Any]] = {}

        if hasattr(xt, "get_instrument_detail_list"):
            symbols = to_xt_symbols(bare_codes)
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i : i + batch_size]
                try:
                    details = xt.get_instrument_detail_list(batch) or {}
                except Exception as exc:
                    logger.warning("get_instrument_detail_list 批次失败: %s", exc)
                    details = {}
                for sym, detail in details.items():
                    if isinstance(detail, dict):
                        details_map[normalize_symbol(sym)] = detail
            return details_map

        for bare in bare_codes:
            detail = self.get_instrument_detail(bare)
            if detail:
                details_map[bare] = detail
        return details_map

    @staticmethod
    def _sw1_display_name(sector_name: str) -> str:
        if sector_name.startswith("1000SW1"):
            return sector_name[len("1000SW1") :]
        if sector_name.startswith("SW1"):
            return sector_name[len("SW1") :]
        return sector_name

    @staticmethod
    def _sector_query_names(sector_name: str) -> list[str]:
        names = [sector_name]
        if sector_name.startswith("1000SW1"):
            names.append(f"SW1{sector_name[len('1000SW1'):]}")
        elif sector_name.startswith("SW1"):
            names.append(f"1000SW1{sector_name[len('SW1'):]}")
        return list(dict.fromkeys(names))

    def get_sw1_industry_map(self, *, force_refresh: bool = False) -> dict[str, str]:
        """构建申万一级行业映射 {裸代码: 行业名}。"""
        if not force_refresh and self._sw1_industry_cache is not None:
            return self._sw1_industry_cache

        self.ensure_connected()
        xt = self.client.xtdata

        if hasattr(xt, "download_sector_data"):
            try:
                xt.download_sector_data()
            except Exception as exc:
                logger.warning("download_sector_data 失败: %s", exc)

        if not hasattr(xt, "get_sector_list") or not hasattr(xt, "get_stock_list_in_sector"):
            self._sw1_industry_cache = {}
            return {}

        sectors = xt.get_sector_list() or []
        industry_sectors = [
            s for s in sectors
            if isinstance(s, str) and (s.startswith("SW1") or s.startswith("1000SW1"))
        ]

        result: dict[str, str] = {}
        matched_sectors = 0
        for sector in industry_sectors:
            display = self._sw1_display_name(sector)
            stocks: list[Any] = []
            for query_name in self._sector_query_names(sector):
                try:
                    stocks = xt.get_stock_list_in_sector(query_name) or []
                except Exception:
                    continue
                if stocks:
                    break
            if not stocks:
                continue

            matched_sectors += 1
            for code in stocks:
                bare = normalize_symbol(str(code))
                result.setdefault(bare, display)

        self._sw1_industry_cache = result
        logger.info(
            "申万一级行业映射: %d/%d 个板块, %d 只股票",
            matched_sectors,
            len(industry_sectors),
            len(result),
        )
        return result

    def get_sector_stocks(self, sector_name: str) -> list[str]:
        """
        获取板块成分股（裸代码）。

        常见板块: 沪深300, 中证500, 上证50 等，名称取决于 QMT 板块库。
        """
        self.ensure_connected()
        xt = self.client.xtdata
        if not hasattr(xt, "get_stock_list_in_sector"):
            raise RuntimeError("当前 xtquant 版本不支持 get_stock_list_in_sector")
        raw = xt.get_stock_list_in_sector(sector_name) or []
        return [normalize_symbol(c) for c in raw]

    def get_index_constituents(
        self,
        index_code: str,
        *,
        sector_fallback: str | None = None,
    ) -> list[str]:
        """获取指数成分股。优先用 get_index_weight，否则回退板块接口。"""
        self.ensure_connected()
        xt = self.client.xtdata
        symbol = to_xt_symbol(index_code)

        if hasattr(xt, "get_index_weight"):
            weights = xt.get_index_weight(symbol) or {}
            if weights:
                return [normalize_symbol(c) for c in weights.keys()]

        if sector_fallback and hasattr(xt, "get_stock_list_in_sector"):
            raw = xt.get_stock_list_in_sector(sector_fallback) or []
            return [normalize_symbol(c) for c in raw]

        return []

    # ── 组合接口（供策略 / 股票池使用）────────────────────────────────────

    def fetch_pool_snapshot(
        self,
        stock_list: Iterable[str],
        *,
        period: Period = "1d",
        bar_count: int = 21,
        download: bool = True,
    ) -> pd.DataFrame:
        """
        拉取股票池快照：最新价、20 日动量、成交额等。

        返回列: symbol, name, close, pct_change, momentum_20d, amount
        """
        codes = list(stock_list)
        if download:
            self.download_kline(codes, period=period, incrementally=True)

        df = self.get_kline(codes, period=period, count=bar_count + 1)
        if df.empty:
            return pd.DataFrame(
                columns=["symbol", "name", "close", "pct_change", "momentum_20d", "amount"],
            )

        rows: list[dict[str, Any]] = []
        for symbol, group in df.groupby("symbol"):
            group = group.sort_values("time")
            if len(group) < 2:
                continue
            last = group.iloc[-1]
            prev = group.iloc[-2]
            first = group.iloc[0]

            close = float(last.get("close", 0))
            prev_close = float(prev.get("close", close))
            base_close = float(first.get("close", close))
            pct = (close / prev_close - 1) * 100 if prev_close else 0.0
            mom = (close / base_close - 1) * 100 if base_close else 0.0

            detail = self.get_instrument_detail(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "name": detail.get("InstrumentName") or detail.get("name") or "",
                    "close": close,
                    "pct_change": round(pct, 2),
                    "momentum_20d": round(mom, 2),
                    "amount": float(last.get("amount", 0)),
                },
            )

        return pd.DataFrame(rows)

    def export_kline_csv(
        self,
        stock_list: Iterable[str],
        output_path: str,
        **kwargs: Any,
    ) -> str:
        df = self.get_kline(stock_list, **kwargs)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    # ── 内部工具 ────────────────────────────────────────────────────────────

    @staticmethod
    def _market_data_to_df(
        raw: dict[str, Any],
        symbols: list[str],
        fields: list[str],
    ) -> pd.DataFrame:
        """将 xtquant 返回转为 long DataFrame。兼容 v3 与 v4 两种结构。"""
        if not raw:
            return pd.DataFrame()

        sample = next(iter(raw.values()))
        if not isinstance(sample, pd.DataFrame):
            return pd.DataFrame()

        first_key = next(iter(raw.keys()))

        # v4: { "600519.SH": DataFrame(index=time, columns=fields) }
        if MinQmtDataFetcher._is_stock_keyed(raw, symbols):
            frames: list[pd.DataFrame] = []
            for symbol in symbols:
                bare = normalize_symbol(symbol)
                df = MinQmtDataFetcher._pick_stock_frame(raw, symbol, bare)
                if df is None or df.empty:
                    continue
                part = df.copy()
                if part.index.name in (None, "index", "stime"):
                    part = part.reset_index()
                    idx_col = part.columns[0]
                    part = part.rename(columns={idx_col: "time"})
                elif "time" not in part.columns:
                    part = part.reset_index().rename(columns={"index": "time"})
                part["symbol"] = bare
                frames.append(part)
            if not frames:
                return pd.DataFrame()
            return pd.concat(frames, ignore_index=True).sort_values(
                ["symbol", "time"],
            ).reset_index(drop=True)

        # v3: { "open": DataFrame(index=time, columns=stock_codes) }
        frames = []
        for symbol in symbols:
            col = symbol if symbol in sample.columns else None
            if col is None:
                bare = normalize_symbol(symbol)
                col = next(
                    (c for c in sample.columns if normalize_symbol(str(c)) == bare),
                    None,
                )
            if col is None:
                continue

            part = pd.DataFrame({"time": sample.index})
            for field_name, field_df in raw.items():
                if isinstance(field_df, pd.DataFrame) and col in field_df.columns:
                    part[field_name] = field_df[col].values
            part["symbol"] = normalize_symbol(symbol)
            frames.append(part)

        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, ignore_index=True).sort_values(
            ["symbol", "time"],
        ).reset_index(drop=True)

    @staticmethod
    def _is_stock_keyed(raw: dict[str, Any], symbols: list[str]) -> bool:
        for key in raw:
            if str(key).endswith((".SH", ".SZ", ".BJ")):
                return True
            if normalize_symbol(str(key)) in {normalize_symbol(s) for s in symbols}:
                return True
        return False

    @staticmethod
    def _pick_stock_frame(
        raw: dict[str, Any],
        symbol: str,
        bare: str,
    ) -> pd.DataFrame | None:
        if symbol in raw:
            val = raw[symbol]
            return val if isinstance(val, pd.DataFrame) else None
        xt = to_xt_symbol(bare)
        if xt in raw:
            val = raw[xt]
            return val if isinstance(val, pd.DataFrame) else None
        for key, val in raw.items():
            if normalize_symbol(str(key)) == bare and isinstance(val, pd.DataFrame):
                return val
        return None

    @staticmethod
    def now_tag() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
