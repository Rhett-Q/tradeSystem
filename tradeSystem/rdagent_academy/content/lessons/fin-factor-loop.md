# fin_factor 四步循环

每次 `rdagent fin_factor` 会按轮次（Loop）推进。每一轮通常包含四个步骤：

```
提假设 → 写代码 → 回测 → 反馈
(direct_exp_gen) (coding) (running) (feedback)
```

## 各步在做什么

1. **提假设**：LLM 根据历史反馈提出新的因子想法（可检验的陈述）。  
2. **写代码**：把想法落成可在 Qlib 中计算的因子实现。  
3. **回测**：在 Docker 里跑量化回测（耗时与数据量、镜像状态有关）。  
4. **反馈**：看 IC、收益等指标，决定本轮假设是否被接受，并写入下一轮上下文。

## 本机怎么观察

- Session 目录：`rdagent/log/<时间戳>/`  
- Checkpoint：`.../__session__/<loop>/<步骤文件>`  
- 状态摘要：`rdagent/session_status.json`（脚本 `rdagent_status.cmd` 会刷新）  
- 图表：官方 Streamlit UI（需 `MLFLOW_ALLOW_FILE_STORE=true`）

## 轮数控制

在 `rdagent/.env` 设置：

```
RDAGENT_MAX_LOOP=2
```

新手建议先 **2 轮**，确认链路通、能产生 feedback，再加长。中断后可用「恢复」从最近 checkpoint 继续，不必从头烧额度。
