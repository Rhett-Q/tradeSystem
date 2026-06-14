#!/usr/bin/env python3
"""全市场数据同步：首次全量 + 每日增量。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from minqmt.sync import MarketDataSync, SyncProgress


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MiniQMT 全市场数据同步")
    p.add_argument(
        "mode",
        choices=["full", "incremental", "universe"],
        help="full=全量历史; incremental=每日增量; universe=列出标的数",
    )
    p.add_argument("--start", default="20200101", help="全量起始 YYYYMMDD")
    p.add_argument("--period", default="1d", help="K 线周期")
    p.add_argument("--batch", type=int, default=200, help="每批下载数量")
    return p.parse_args()


def on_progress(p: SyncProgress) -> None:
    print(f"  [{p.phase}] {p.done}/{p.total} ({p.pct:.1f}%) · {p.message}")


def main() -> int:
    args = parse_args()
    sync = MarketDataSync()

    try:
        sync.ensure_ready()
    except (ConnectionError, RuntimeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    if args.mode == "universe":
        codes = sync.get_universe()
        print(f"全市场标的: {len(codes)} 只")
        print(", ".join(codes[:20]), "..." if len(codes) > 20 else "")
        return 0

    if args.mode == "full":
        print(f"开始全量同步 · start={args.start} · period={args.period}")
        report = sync.sync_full_market(
            start_time=args.start,
            period=args.period,
            batch_size=args.batch,
            on_progress=on_progress,
        )
    else:
        print(f"开始增量同步 · period={args.period}")
        report = sync.sync_daily_incremental(
            period=args.period,
            batch_size=args.batch,
            on_progress=on_progress,
        )

    print(
        f"\n[完成] {report.mode} · {report.success_count}/{report.stock_count} 成功"
        f" · 失败 {report.failed_count}\n  {report.started_at} → {report.finished_at}",
    )
    return 0 if report.failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
