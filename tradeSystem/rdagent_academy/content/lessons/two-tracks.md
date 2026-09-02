# 生产轨 vs 研究轨

TradeSystem 故意把两条路分开，避免「研究实验弄坏生产数据管道」。

## 对照表

| | 生产轨 (Route A) | 研究轨 (RD-Agent) |
|---|---|---|
| Python | backend（约 3.9+） | `rdagent/.venv`（**3.10+ / 3.11**） |
| 数据 | PostgreSQL `kline_daily` | Qlib `cn_data` 或 PG 导出 |
| 因子 | `expression.py` + Alpha158 等 | LLM 生成 + Qlib 回测 |
| UI | TradeSystem Vue | Streamlit（19899）+ 本 Academy |
| 目标 | 稳定选股 / 回测 / 同步 | 探索新因子，人工采纳后再入库 |

## 记住三句话

1. **不要**用 RD-Agent 的 venv 去跑 backend。  
2. **fin_factor** 依赖 Docker 镜像 `local_qlib`，首次构建很慢，建议先「预生成因子数据」。  
3. 研究产出要进生产，需人工审阅后再接到 catalog / 自定义因子。

## 数据怎么对齐

- **方案 A（推荐新手）**：官方 `~/.qlib/qlib_data/cn_data`（下载快，数据偏旧到约 2020）。  
- **方案 B（对齐生产）**：`export_pg_qlib.cmd` 从 PostgreSQL 导出；当前仓库里可能只有 5 只样本，全量导出后再给 RD-Agent。

在实验室页可以一键检查这两条数据路径。
