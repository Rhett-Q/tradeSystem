from __future__ import annotations

from typing import Any

LIBRARY_ALPHA158 = "alpha158"
LIBRARY_ALPHA360 = "alpha360"
DEFAULT_LIBRARY = LIBRARY_ALPHA158

SUPPORTED_LIBRARIES: dict[str, str] = {
    LIBRARY_ALPHA158: "Alpha158",
    LIBRARY_ALPHA360: "Alpha360",
}

# Alpha158 默认配置（与 qlib.contrib.data.loader.Alpha158DL 一致）
_ALPHA158_CONFIG: dict[str, Any] = {
    "kbar": {},
    "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW", "VWAP"]},
    "rolling": {},
}


def normalize_library(library: str = "") -> str:
    key = (library or DEFAULT_LIBRARY).strip().lower()
    if key in ("158", "alpha158", "alpha_158"):
        return LIBRARY_ALPHA158
    if key in ("360", "alpha360", "alpha_360"):
        return LIBRARY_ALPHA360
    if key in SUPPORTED_LIBRARIES:
        return key
    raise ValueError(f"未知因子库: {library}，支持 alpha158 / alpha360")


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
        result.append((name, expr, _guess_category_alpha158(name)))
    return result


def _build_alpha360_fields() -> list[tuple[str, str, str]]:
    try:
        from qlib.contrib.data.loader import Alpha360DL

        fields, names = Alpha360DL.get_feature_config()
        items = list(zip(names, fields))
    except ImportError:
        items = _embedded_alpha360_fields()

    return [(name, expr, _guess_category_alpha360(name)) for name, expr in items]


def _embedded_alpha360_fields() -> list[tuple[str, str]]:
    fields: list[str] = []
    names: list[str] = []

    for i in range(59, 0, -1):
        fields.append(f"Ref($close, {i})/$close")
        names.append(f"CLOSE{i}")
    fields.append("$close/$close")
    names.append("CLOSE0")

    for i in range(59, 0, -1):
        fields.append(f"Ref($open, {i})/$close")
        names.append(f"OPEN{i}")
    fields.append("$open/$close")
    names.append("OPEN0")

    for i in range(59, 0, -1):
        fields.append(f"Ref($high, {i})/$close")
        names.append(f"HIGH{i}")
    fields.append("$high/$close")
    names.append("HIGH0")

    for i in range(59, 0, -1):
        fields.append(f"Ref($low, {i})/$close")
        names.append(f"LOW{i}")
    fields.append("$low/$close")
    names.append("LOW0")

    for i in range(59, 0, -1):
        fields.append(f"Ref($vwap, {i})/$close")
        names.append(f"VWAP{i}")
    fields.append("$vwap/$close")
    names.append("VWAP0")

    for i in range(59, 0, -1):
        fields.append(f"Ref($volume, {i})/($volume+1e-12)")
        names.append(f"VOLUME{i}")
    fields.append("$volume/($volume+1e-12)")
    names.append("VOLUME0")

    return list(zip(names, fields))


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


def re_match_prefix(name: str) -> str:
    i = 0
    while i < len(name) and not name[i].isdigit():
        i += 1
    return name[:i]


def _guess_category_alpha158(name: str) -> str:
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


def _guess_category_alpha360(name: str) -> str:
    prefix = re_match_prefix(name)
    mapping = {
        "CLOSE": "close_series",
        "OPEN": "open_series",
        "HIGH": "high_series",
        "LOW": "low_series",
        "VWAP": "vwap_series",
        "VOLUME": "volume_series",
    }
    return mapping.get(prefix, "other")


def _guess_category(name: str, library: str = LIBRARY_ALPHA158) -> str:
    if library == LIBRARY_ALPHA360:
        return _guess_category_alpha360(name)
    return _guess_category_alpha158(name)


_CATALOGS: dict[str, list[tuple[str, str, str]]] = {}
_EXPR_BY_LIBRARY: dict[str, dict[str, str]] = {}


def _build_catalog(library: str) -> list[tuple[str, str, str]]:
    if library == LIBRARY_ALPHA360:
        return _build_alpha360_fields()
    return _build_alpha158_fields()


def _ensure_catalog(library: str = DEFAULT_LIBRARY) -> None:
    lib = normalize_library(library)
    if lib not in _CATALOGS:
        _CATALOGS[lib] = _build_catalog(lib)
        _EXPR_BY_LIBRARY[lib] = {name: expr for name, expr, _ in _CATALOGS[lib]}


def get_factor_expression(name: str, library: str = "") -> str | None:
    if library:
        lib = normalize_library(library)
        _ensure_catalog(lib)
        return _EXPR_BY_LIBRARY[lib].get(name)

    for lib in (LIBRARY_ALPHA158, LIBRARY_ALPHA360):
        _ensure_catalog(lib)
        expr = _EXPR_BY_LIBRARY[lib].get(name)
        if expr:
            return expr
    return None


def resolve_factor_library(name: str, library: str = "") -> str | None:
    """返回因子所在库；指定 library 时仅在该库查找。"""
    if library:
        lib = normalize_library(library)
        _ensure_catalog(lib)
        return lib if name in _EXPR_BY_LIBRARY[lib] else None

    for lib in (LIBRARY_ALPHA158, LIBRARY_ALPHA360):
        _ensure_catalog(lib)
        if name in _EXPR_BY_LIBRARY[lib]:
            return lib
    return None


def list_libraries() -> list[dict[str, Any]]:
    qlib_available = False
    try:
        import qlib  # noqa: F401

        qlib_available = True
    except ImportError:
        pass

    items = []
    for key, label in SUPPORTED_LIBRARIES.items():
        _ensure_catalog(key)
        items.append({
            "id": key,
            "label": label,
            "factor_count": len(_CATALOGS[key]),
        })
    return {"libraries": items, "qlib_installed": qlib_available, "default": DEFAULT_LIBRARY}


def list_factor_catalog(category: str = "", library: str = DEFAULT_LIBRARY) -> dict[str, Any]:
    from services.qlib.factor_meta import CATEGORY_HELP, enrich_factor, list_usage_examples

    lib = normalize_library(library)
    _ensure_catalog(lib)
    catalog = _CATALOGS[lib]

    cats: dict[str, list[dict[str, Any]]] = {}
    for name, expr, cat in catalog:
        if category and cat != category:
            continue
        cats.setdefault(cat, []).append(
            enrich_factor({"name": name, "expression": expr, "category": cat}, library=lib),
        )

    qlib_available = False
    try:
        import qlib  # noqa: F401

        qlib_available = True
    except ImportError:
        pass

    category_help = dict(CATEGORY_HELP)
    if lib == LIBRARY_ALPHA360:
        category_help.update({
            "close_series": "收盘价序列：过去 60 日收盘价相对最新收盘归一化（CLOSE59…CLOSE0）。",
            "open_series": "开盘价序列：过去 60 日开盘价相对最新收盘归一化。",
            "high_series": "最高价序列：过去 60 日最高价相对最新收盘归一化。",
            "low_series": "最低价序列：过去 60 日最低价相对最新收盘归一化。",
            "vwap_series": "VWAP 序列：过去 60 日均价相对最新收盘归一化。",
            "volume_series": "成交量序列：过去 60 日成交量相对最新成交量归一化。",
        })

    return {
        "library": SUPPORTED_LIBRARIES[lib],
        "library_id": lib,
        "qlib_installed": qlib_available,
        "categories": sorted(cats.keys()),
        "category_help": category_help,
        "usage_examples": list_usage_examples() if lib == LIBRARY_ALPHA158 else [],
        "factors": [item for items in cats.values() for item in items],
        "total": sum(len(v) for v in cats.values()),
    }


def list_factor_names(library: str = "") -> list[str]:
    if library:
        lib = normalize_library(library)
        _ensure_catalog(lib)
        return [name for name, _, _ in _CATALOGS[lib]]
    names: list[str] = []
    for lib in SUPPORTED_LIBRARIES:
        _ensure_catalog(lib)
        names.extend(name for name, _, _ in _CATALOGS[lib])
    return names
