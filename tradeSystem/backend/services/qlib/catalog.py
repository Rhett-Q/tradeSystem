from __future__ import annotations

from typing import Any

# Alpha158 默认配置（与 qlib.contrib.data.loader.Alpha158DL 一致）
_ALPHA158_CONFIG: dict[str, Any] = {
    "kbar": {},
    "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW", "VWAP"]},
    "rolling": {},
}


def _build_alpha158_fields() -> list[tuple[str, str, str]]:
    """返回 (name, expression, category) 列表。"""
    try:
        from qlib.contrib.data.loader import Alpha158DL

        fields, names = Alpha158DL.get_feature_config(_ALPHA158_CONFIG)
        items = list(zip(names, fields))
    except ImportError:
        items = _embedded_alpha158_fields()

    result: list[tuple[str, str, str]] = []
    for name, expr in items:
        result.append((name, expr, _guess_category(name)))
    return result


def _embedded_alpha158_fields() -> list[tuple[str, str]]:
    """无 pyqlib 时使用内嵌 Alpha158 定义。"""
    config = _ALPHA158_CONFIG
    fields: list[str] = []
    names: list[str] = []

    if "kbar" in config:
        fields += [
            "($close-$open)/$open",
            "($high-$low)/$open",
            "($close-$open)/($high-$low+1e-12)",
            "($high-Greater($open, $close))/$open",
            "($high-Greater($open, $close))/($high-$low+1e-12)",
            "(Less($open, $close)-$low)/$open",
            "(Less($open, $close)-$low)/($high-$low+1e-12)",
            "(2*$close-$high-$low)/$open",
            "(2*$close-$high-$low)/($high-$low+1e-12)",
        ]
        names += ["KMID", "KLEN", "KMID2", "KUP", "KUP2", "KLOW", "KLOW2", "KSFT", "KSFT2"]

    if "price" in config:
        windows = config["price"].get("windows", range(5))
        feature = config["price"].get("feature", ["OPEN", "HIGH", "LOW", "CLOSE", "VWAP"])
        for field in feature:
            fld = field.lower()
            for d in windows:
                fields.append(f"Ref(${fld}, {d})/$close" if d else f"${fld}/$close")
                names.append(f"{field.upper()}{d}")

    windows = [5, 10, 20, 30, 60]
    rolling_ops = [
        ("ROC", lambda d: (f"Ref($close, {d})/$close", f"ROC{d}")),
        ("MA", lambda d: (f"Mean($close, {d})/$close", f"MA{d}")),
        ("STD", lambda d: (f"Std($close, {d})/$close", f"STD{d}")),
        ("BETA", lambda d: (f"Slope($close, {d})/$close", f"BETA{d}")),
        ("RSQR", lambda d: (f"Rsquare($close, {d})", f"RSQR{d}")),
        ("RESI", lambda d: (f"Resi($close, {d})/$close", f"RESI{d}")),
        ("MAX", lambda d: (f"Max($high, {d})/$close", f"MAX{d}")),
        ("MIN", lambda d: (f"Min($low, {d})/$close", f"MIN{d}")),
        ("QTLU", lambda d: (f"Quantile($close, {d}, 0.8)/$close", f"QTLU{d}")),
        ("QTLD", lambda d: (f"Quantile($close, {d}, 0.2)/$close", f"QTLD{d}")),
        ("RSV", lambda d: (
            f"($close-Min($low, {d}))/(Max($high, {d})-Min($low, {d})+1e-12)",
            f"RSV{d}",
        )),
        ("IMAX", lambda d: (f"IdxMax($high, {d})/{d}", f"IMAX{d}")),
        ("IMIN", lambda d: (f"IdxMin($low, {d})/{d}", f"IMIN{d}")),
        ("IMXD", lambda d: (f"(IdxMax($high, {d})-IdxMin($low, {d}))/{d}", f"IMXD{d}")),
        ("CORR", lambda d: (f"Corr($close, Log($volume+1), {d})", f"CORR{d}")),
        ("CORD", lambda d: (
            f"Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), {d})",
            f"CORD{d}",
        )),
        ("CNTP", lambda d: (f"Mean($close>Ref($close, 1), {d})", f"CNTP{d}")),
        ("CNTN", lambda d: (f"Mean($close<Ref($close, 1), {d})", f"CNTN{d}")),
        ("CNTD", lambda d: (
            f"Mean($close>Ref($close, 1), {d})-Mean($close<Ref($close, 1), {d})",
            f"CNTD{d}",
        )),
        ("SUMP", lambda d: (
            f"Sum(Greater($close-Ref($close, 1), 0), {d})/(Sum(Abs($close-Ref($close, 1)), {d})+1e-12)",
            f"SUMP{d}",
        )),
        ("SUMN", lambda d: (
            f"Sum(Greater(Ref($close, 1)-$close, 0), {d})/(Sum(Abs($close-Ref($close, 1)), {d})+1e-12)",
            f"SUMN{d}",
        )),
        ("SUMD", lambda d: (
            f"(Sum(Greater($close-Ref($close, 1), 0), {d})-Sum(Greater(Ref($close, 1)-$close, 0), {d}))"
            f"/(Sum(Abs($close-Ref($close, 1)), {d})+1e-12)",
            f"SUMD{d}",
        )),
        ("VMA", lambda d: (f"Mean($volume, {d})/($volume+1e-12)", f"VMA{d}")),
        ("VSTD", lambda d: (f"Std($volume, {d})/($volume+1e-12)", f"VSTD{d}")),
        ("WVMA", lambda d: (
            f"Std(Abs($close/Ref($close, 1)-1)*$volume, {d})/(Mean(Abs($close/Ref($close, 1)-1)*$volume, {d})+1e-12)",
            f"WVMA{d}",
        )),
        ("VSUMP", lambda d: (
            f"Sum(Greater($volume-Ref($volume, 1), 0), {d})/(Sum(Abs($volume-Ref($volume, 1)), {d})+1e-12)",
            f"VSUMP{d}",
        )),
        ("VSUMN", lambda d: (
            f"Sum(Greater(Ref($volume, 1)-$volume, 0), {d})/(Sum(Abs($volume-Ref($volume, 1)), {d})+1e-12)",
            f"VSUMN{d}",
        )),
        ("VSUMD", lambda d: (
            f"(Sum(Greater($volume-Ref($volume, 1), 0), {d})-Sum(Greater(Ref($volume, 1)-$volume, 0), {d}))"
            f"/(Sum(Abs($volume-Ref($volume, 1)), {d})+1e-12)",
            f"VSUMD{d}",
        )),
    ]
    for _, builder in rolling_ops:
        for d in windows:
            expr, nm = builder(d)
            fields.append(expr)
            names.append(nm)

    return list(zip(names, fields))


def _guess_category(name: str) -> str:
    if name.startswith("K"):
        return "kbar"
    if name in {"OPEN0", "HIGH0", "LOW0", "VWAP0", "CLOSE0"} or name.endswith("0") and name[:-1] in {
        "OPEN", "HIGH", "LOW", "VWAP", "VOLUME",
    }:
        return "price"
    prefix = re_match_prefix(name)
    mapping = {
        "ROC": "momentum",
        "MA": "trend",
        "STD": "volatility",
        "BETA": "trend",
        "RSQR": "trend",
        "RESI": "trend",
        "MAX": "range",
        "MIN": "range",
        "QTL": "range",
        "RSV": "range",
        "IMX": "aroon",
        "CORR": "volume",
        "CORD": "volume",
        "CNT": "momentum",
        "SUM": "momentum",
        "VM": "volume",
        "VS": "volume",
        "WV": "volume",
    }
    for key, cat in mapping.items():
        if prefix.startswith(key):
            return cat
    return "other"


def re_match_prefix(name: str) -> str:
    i = 0
    while i < len(name) and not name[i].isdigit():
        i += 1
    return name[:i]


_CATALOG: list[tuple[str, str, str]] | None = None
_EXPR_BY_NAME: dict[str, str] | None = None


def _ensure_catalog() -> None:
    global _CATALOG, _EXPR_BY_NAME
    if _CATALOG is None:
        _CATALOG = _build_alpha158_fields()
        _EXPR_BY_NAME = {name: expr for name, expr, _ in _CATALOG}


def get_factor_expression(name: str) -> str | None:
    _ensure_catalog()
    assert _EXPR_BY_NAME is not None
    return _EXPR_BY_NAME.get(name)


def list_factor_catalog(category: str = "") -> dict[str, Any]:
    from services.qlib.factor_meta import CATEGORY_HELP, enrich_factor, list_usage_examples

    _ensure_catalog()
    assert _CATALOG is not None
    cats: dict[str, list[dict[str, Any]]] = {}
    for name, expr, cat in _CATALOG:
        if category and cat != category:
            continue
        cats.setdefault(cat, []).append(
            enrich_factor({"name": name, "expression": expr, "category": cat}),
        )

    qlib_available = False
    try:
        import qlib  # noqa: F401

        qlib_available = True
    except ImportError:
        pass

    return {
        "library": "Alpha158",
        "qlib_installed": qlib_available,
        "categories": sorted(cats.keys()),
        "category_help": CATEGORY_HELP,
        "usage_examples": list_usage_examples(),
        "factors": [item for items in cats.values() for item in items],
        "total": sum(len(v) for v in cats.values()),
    }
