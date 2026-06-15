from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from services.qlib.dataset import build_training_dataset
from services.qlib.train_log import TrainLogger, TrainingFailedError

_MODELS_DIR = Path(__file__).resolve().parents[2] / "data" / "models"
_MIN_SAMPLES = 200


def _ensure_models_dir() -> Path:
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return _MODELS_DIR


def _build_model(params: dict[str, Any], log: TrainLogger):
    try:
        import lightgbm as lgb

        model = lgb.LGBMRegressor(
            n_estimators=int(params.get("n_estimators", 200)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_depth=int(params.get("max_depth", 6)),
            subsample=float(params.get("subsample", 0.8)),
            colsample_bytree=float(params.get("colsample_bytree", 0.8)),
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        log.info("模型后端 · LightGBM LGBMRegressor")
        return model, "lightgbm"
    except ImportError:
        from sklearn.ensemble import GradientBoostingRegressor

        log.warn("未安装 lightgbm，回退 sklearn GradientBoostingRegressor")
        model = GradientBoostingRegressor(
            n_estimators=int(params.get("n_estimators", 100)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_depth=int(params.get("max_depth", 4)),
            random_state=42,
        )
        return model, "sklearn_gbr"


def list_models() -> list[dict[str, Any]]:
    root = _ensure_models_dir()
    items: list[dict[str, Any]] = []
    for meta_path in sorted(root.glob("*.meta.json"), reverse=True):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            items.append(meta)
        except (json.JSONDecodeError, OSError):
            continue
    return items


def get_model_meta(model_id: str) -> dict[str, Any] | None:
    path = _ensure_models_dir() / f"{model_id}.meta.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_model(model_id: str):
    try:
        import joblib
    except ImportError as exc:
        raise RuntimeError("请安装 joblib: pip install joblib") from exc
    root = _ensure_models_dir()
    model_path = root / f"{model_id}.joblib"
    if not model_path.is_file():
        raise FileNotFoundError(f"模型不存在: {model_id}")
    return joblib.load(model_path)


def train_model(
    *,
    library: str = "alpha158",
    factors: list[str] | None = None,
    start_date: str,
    end_date: str,
    label_days: int = 5,
    market: str = "",
    sector: str = "",
    train_ratio: float = 0.8,
    params: dict[str, Any] | None = None,
    max_symbols: int = 800,
) -> dict[str, Any]:
    log = TrainLogger("train")
    log.info("开始模型训练")
    log.set_stat("library", library)
    log.set_stat("train_ratio", train_ratio)

    try:
        x, y, ds_meta = build_training_dataset(
            library=library,
            factors=factors,
            start_date=start_date,
            end_date=end_date,
            label_days=label_days,
            market=market,
            sector=sector,
            max_symbols=max_symbols,
            log=log,
        )
    except ValueError as exc:
        log.error(str(exc))
        raise TrainingFailedError(str(exc), log) from exc
    except Exception as exc:
        log.error(f"数据集构建异常 · {type(exc).__name__}: {exc}")
        log.error(traceback.format_exc())
        raise TrainingFailedError(f"数据集构建失败: {exc}", log) from exc

    if len(x) < _MIN_SAMPLES:
        msg = (
            f"训练样本过少 ({len(x)} < {_MIN_SAMPLES})。"
            f"请扩大日期范围、增大 max_symbols，或换用 alpha158（特征更少）。"
            f"当前：{ds_meta['symbols']} 只 · {ds_meta['start_date']}~{ds_meta['end_date']}"
        )
        raise TrainingFailedError(msg, log)

    split = int(len(x) * train_ratio)
    if split < 50 or len(x) - split < 20:
        msg = f"训练/验证切分无效 · 总样本 {len(x)} · train_ratio={train_ratio}"
        raise TrainingFailedError(msg, log)

    x_train, x_valid = x.iloc[:split], x.iloc[split:]
    y_train, y_valid = y.iloc[:split], y.iloc[split:]
    log.info(f"样本切分 · 训练 {len(x_train):,} · 验证 {len(x_valid):,} · ratio={train_ratio}")

    try:
        model, backend = _build_model(params or {}, log)
        log.info("开始 fit …")
        model.fit(x_train, y_train)
        log.info("fit 完成 · 开始验证集预测")
        pred_valid = model.predict(x_valid)
    except Exception as exc:
        log.error(f"模型训练异常 · {type(exc).__name__}: {exc}")
        log.error(traceback.format_exc())
        raise TrainingFailedError(f"模型训练失败: {exc}", log) from exc

    mse = float(np.mean((pred_valid - y_valid) ** 2))
    ic = float(np.corrcoef(pred_valid, y_valid)[0, 1]) if len(y_valid) > 2 else None
    ic_display = f"{ic:.6f}" if ic is not None and not np.isnan(ic) else "N/A"
    log.info(f"验证指标 · MSE={mse:.8f} · IC={ic_display}")

    model_id = uuid.uuid4().hex[:12]
    root = _ensure_models_dir()
    try:
        import joblib
    except ImportError as exc:
        log.error("缺少 joblib，无法保存模型")
        raise TrainingFailedError("请安装 joblib: pip install joblib", log) from exc

    model_path = root / f"{model_id}.joblib"
    joblib.dump(model, model_path)
    log.info(f"模型已保存 · {model_path.name} · backend={backend}")

    meta = {
        "id": model_id,
        "backend": backend,
        "library_id": ds_meta["library_id"],
        "factors": ds_meta["factors"],
        "factor_count": ds_meta.get("factor_count", len(ds_meta["factors"])),
        "start_date": ds_meta["start_date"],
        "end_date": ds_meta["end_date"],
        "label_days": label_days,
        "market": market,
        "sector": sector,
        "samples": ds_meta["samples"],
        "symbols": ds_meta["symbols"],
        "lookback_days": ds_meta.get("lookback_days"),
        "train_samples": len(x_train),
        "valid_samples": len(x_valid),
        "valid_mse": round(mse, 8),
        "valid_ic": round(ic, 6) if ic is not None and not np.isnan(ic) else None,
        "label_stats": ds_meta.get("label_stats"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (root / f"{model_id}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log.finish(f"训练完成 · model_id={model_id}")
    return log.attach(meta)
