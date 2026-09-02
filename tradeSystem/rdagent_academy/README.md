# RD-Agent Academy

独立学习站（**B + L2**）：面向新手讲解 RD-Agent，并在网页上操作本机 `tradeSystem/scripts` 脚本。

- 前端：http://127.0.0.1:19901  
- API：http://127.0.0.1:19900  
- 官方 Streamlit UI（可选）：http://localhost:19899  

与 TradeSystem 主站（5173）分离，不混用生产轨 UI。

## 功能

| 区域 | 能力 |
|------|------|
| 课程 / 流程地图 | 中文导览：概念、双轨、四步 Loop、数据与 Session |
| 健康检查 | 探测 venv / .env / LLM / Docker / cn_data / HDF5 / 导出 |
| 数据 | 下载官方 cn_data、预生成因子 HDF5、PG→Qlib 导出 |
| 运行台 | 新开跑 / 恢复 `fin_factor`，实时任务日志 |
| Sessions | 列出历史实验、读 feedback、一键开 Streamlit |

## 启动

```cmd
tradeSystem\rdagent_academy\scripts\setup_academy.cmd
tradeSystem\rdagent_academy\scripts\run_academy.cmd
```

浏览器打开 http://127.0.0.1:19901

前置：本机已能跑 `scripts\rdagent_setup.cmd`（研究轨 venv）。开跑还需 Docker + LLM Key + cn_data。

## 目录

```
rdagent_academy/
├── backend/          FastAPI 包装 scripts
├── frontend/         Vite + Vue 学习站
├── content/          课程 Markdown + curriculum.json
└── scripts/          setup / run
```

## 安全说明

本控制台只绑定 `127.0.0.1`，会在本机拉起长时间任务并写日志目录。不要暴露到公网。
