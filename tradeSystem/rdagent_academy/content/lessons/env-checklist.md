# 环境检查清单

在实验室打开 **健康检查**，目标是让「可学习」与「可开跑」两项尽可能变绿。

## 必过项（开跑前）

1. `rdagent/.venv` 已创建（`scripts\rdagent_setup.cmd`）  
2. `rdagent/.env` 存在且含 LLM Key  
3. Docker Desktop 正在运行  
4. 官方 cn_data 已下载（`calendars/day.txt` 存在）  
5. Windows：**开发人员模式**已开（允许 symlink），否则 `fin_factor` 会报 WinError 1314  

## 强烈建议

- 先跑 **预生成因子 HDF5**，避免首次 Docker 卡 30+ 分钟  
- 终端用仓库提供的 `scripts\*.cmd`（已 `chcp 65001`），减少中文乱码  

## 本页操作

右侧实验室 →「运行 health_check」会调用现有 `rdagent_health.cmd`。失败时按检查项 hint 逐项修，不要一上来猛开 fin_factor。
