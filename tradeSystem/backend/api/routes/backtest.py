from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import require_db
from services.backtest.backtest_service import run_backtest
from services.backtest.multi_factor_backtest import run_multi_factor_backtest
from services.strategy.service import list_strategies

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class FactorCondition(BaseModel):
    factor: str = Field(..., description="Alpha158 因子名")
    min_value: float | None = None
    max_value: float | None = None


class BacktestRunRequest(BaseModel):
    symbol: str = Field("600519.SH", description="股票代码")
    strategy: str = Field("ma_crossover", description="策略 ID")
    params: dict[str, Any] = Field(default_factory=dict, description="策略参数")
    start_date: str | None = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: str | None = Field(None, description="结束日期 YYYY-MM-DD")
    initial_cash: float = Field(100_000.0, ge=1000)
    commission: float = Field(0.001, ge=0, le=0.05, description="佣金比例")
    stake_pct: float = Field(95.0, ge=1, le=100, description="单次买入资金占比 %")


class MultiBacktestRunRequest(BaseModel):
    symbol: str = Field("600519.SH", description="股票代码")
    conditions: list[FactorCondition] = Field(..., min_length=1, max_length=10)
    start_date: str | None = None
    end_date: str | None = None
    initial_cash: float = Field(100_000.0, ge=1000)
    commission: float = Field(0.001, ge=0, le=0.05)
    stake_pct: float = Field(95.0, ge=1, le=100)


@router.get("/strategies")
def get_strategies(_: None = Depends(require_db)) -> list[dict[str, Any]]:
    return list_strategies()


@router.post("/run")
def run_backtest_api(
    body: BacktestRunRequest,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        if body.strategy == "multi_factor":
            raise HTTPException(
                400,
                "多因子策略请使用 POST /api/backtest/multi-run 并传入 conditions",
            )
        return run_backtest(
            symbol=body.symbol,
            strategy=body.strategy,
            params=body.params,
            start_date=body.start_date,
            end_date=body.end_date,
            initial_cash=body.initial_cash,
            commission=body.commission,
            stake_pct=body.stake_pct,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"回测失败: {exc}") from exc


@router.post("/multi-run")
def run_multi_backtest_api(
    body: MultiBacktestRunRequest,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        conditions = [c.model_dump(exclude_none=True) for c in body.conditions]
        return run_multi_factor_backtest(
            symbol=body.symbol,
            conditions=conditions,
            start_date=body.start_date,
            end_date=body.end_date,
            initial_cash=body.initial_cash,
            commission=body.commission,
            stake_pct=body.stake_pct,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"多因子回测失败: {exc}") from exc
