# 读懂 Session 与反馈

## 目录结构（简化）

```
rdagent/log/2026-06-17_14-24-03-264299/
├── __session__/
│   ├── 0/
│   │   ├── 0_direct_exp_gen
│   │   ├── 1_coding
│   │   ├── 2_running
│   │   └── 3_feedback
│   └── 1/ ...
└── （详细 trace / MLflow 相关产物）
```

## 看什么

| 信号 | 含义 |
|------|------|
| loops_started | 已开始的轮次数 |
| loops_completed | 已写出 feedback 的轮次 |
| latest_step_label | 卡在哪一步（LLM / Docker / 反馈） |
| decision=True | 该轮假设被接受 |

## 官方 UI

实验室可一键启动 Streamlit（`http://localhost:19899`）：

- Log Path 选对应目录  
- 向下滚到 Summary / Feedback 看图表  

若没有回测图，检查 `.env` 是否有 `MLFLOW_ALLOW_FILE_STORE=true`，并需 **重新跑** 才会生成图表数据。

## 和 TradeSystem 的衔接

Session 里表现好的因子，不要自动进生产。流程应是：读懂逻辑 → 人工复核代码 → 再写入自定义因子 / catalog。
