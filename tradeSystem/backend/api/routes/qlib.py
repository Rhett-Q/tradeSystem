from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import require_db
from services.qlib.analysis import compute_factor_ic
from services.qlib.catalog import list_factor_catalog, list_libraries
from services.qlib.predictor import predict_universe
from services.qlib.trainer import list_models, train_model
from services.qlib.train_log import TrainingFailedError

router = APIRouter(prefix="/api/qlib", tags=["qlib"])


class TrainRequest(BaseModel):
    library: str = Field("alpha158", description="alpha158 / alpha360")
    factors: list[str] = Field(default_factory=list, description="空则使用该库全部因子")
    start_date: str
    end_date: str
    label_days: int = Field(5, ge=1, le=20)
    market: str = ""
    sector: str = ""
    train_ratio: float = Field(0.8, ge=0.5, le=0.95)
    max_symbols: int = Field(800, ge=100, le=3000)
    params: dict[str, Any] = Field(default_factory=dict)


class PredictRequest(BaseModel):
    model_id: str
    market: str = ""
    sector: str = ""
    top_n: int = Field(50, ge=1, le=200)


@router.get("/libraries")
def get_libraries(_: None = Depends(require_db)) -> dict[str, Any]:
    return list_libraries()


@router.get("/factors")
def get_factors(
    library: str = Query("alpha158"),
    category: str = Query(""),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    return list_factor_catalog(category.strip(), library=library)


@router.get("/factor-ic")
def factor_ic(
    factor: str = Query(...),
    library: str = Query("alpha158"),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    forward_days: int = Query(5, ge=1, le=20),
    market: str = Query(""),
    sector: str = Query(""),
    quintiles: int = Query(5, ge=3, le=10),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        return compute_factor_ic(
            factor=factor.strip(),
            library=library,
            start_date=start_date,
            end_date=end_date,
            forward_days=forward_days,
            market=market.strip(),
            sector=sector.strip(),
            quintiles=quintiles,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/models")
def get_models(_: None = Depends(require_db)) -> dict[str, Any]:
    return {"models": list_models()}


@router.post("/train")
def train(body: TrainRequest, _: None = Depends(require_db)) -> dict[str, Any]:
    try:
        return train_model(
            library=body.library,
            factors=body.factors or None,
            start_date=body.start_date,
            end_date=body.end_date,
            label_days=body.label_days,
            market=body.market.strip(),
            sector=body.sector.strip(),
            train_ratio=body.train_ratio,
            params=body.params,
            max_symbols=body.max_symbols,
        )
    except TrainingFailedError as exc:
        raise HTTPException(400, detail=exc.payload) from exc
    except Exception as exc:
        raise HTTPException(500, detail={"message": str(exc), "log": []}) from exc


@router.post("/predict")
def predict(body: PredictRequest, _: None = Depends(require_db)) -> dict[str, Any]:
    try:
        return predict_universe(
            model_id=body.model_id.strip(),
            market=body.market.strip(),
            sector=body.sector.strip(),
            top_n=body.top_n,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
