#!/usr/bin/env python3
"""MiniQMT 数据拉取示例脚本。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from minqmt import MinQmtDataFetcher, to_xt_symbol


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MiniQMT 数据获取")
    parser.add_argument(
        "--codes",
        nargs="+",
        default=["600519", "000001", "300750"],
        help="证券代码列表",
    )
    parser.add_argument("--period", default="1d", help="K 线周期: 1d/1m/5m/tick")
    parser.add_argument("--start", default="20240101", help="起始日期 YYYYMMDD")
    parser.add_argument("--end", default="", help="结束日期 YYYYMMDD")
    parser.add_argument("--count", type=int, default=60, help="读取条数")
    parser.add_argument(
        "--action",
        choices=["download", "query", "snapshot", "sector"],
        default="snapshot",
        help="download=仅下载; query=读K线; snapshot=股票池快照; sector=板块成分",
    )
    parser.add_argument("--sector", default="沪深300", help="板块名称")
    parser.add_argument("--output", default="", help="CSV 输出路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetcher = MinQmtDataFetcher()

    try:
        fetcher.ensure_connected()
    except (ConnectionError, RuntimeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    print(f"[OK] MiniQMT 已连接 · {MinQmtDataFetcher.now_tag()}")

    if args.action == "sector":
        stocks = fetcher.get_sector_stocks(args.sector)
        print(json.dumps({"sector": args.sector, "count": len(stocks), "stocks": stocks[:20]}, ensure_ascii=False, indent=2))
        return 0

    codes = args.codes
    xt_codes = [to_xt_symbol(c) for c in codes]
    print(f"标的: {', '.join(xt_codes)}")

    if args.action in ("download", "snapshot"):
        results = fetcher.download_kline(
            codes,
            period=args.period,
            start_time=args.start,
            end_time=args.end,
        )
        for r in results:
            status = "成功" if r.success else "失败"
            print(f"  下载 {r.stock_code} [{r.period}] {status}" + (f" · {r.message}" if r.message else ""))

    if args.action == "query":
        df = fetcher.get_kline(
            codes,
            period=args.period,
            start_time=args.start,
            end_time=args.end,
            count=args.count,
        )
        print(df.tail(10).to_string(index=False))
        if args.output:
            df.to_csv(args.output, index=False, encoding="utf-8-sig")
            print(f"已写入 {args.output}")

    if args.action == "snapshot":
        df = fetcher.fetch_pool_snapshot(codes, period=args.period, bar_count=args.count)
        print(df.to_string(index=False))
        if args.output:
            df.to_csv(args.output, index=False, encoding="utf-8-sig")
            print(f"已写入 {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
