# 回测数据从哪来

RD-Agent 不直接读 PostgreSQL，它需要 **Qlib provider** 目录。

## 路径 A：官方 cn_data

- 位置：`C:\Users\<你>\.qlib\qlib_data\cn_data`  
- 脚本：`rdagent_download_qlib.cmd`  
- 优点：一键、覆盖全市场日线  
- 缺点：官方包通常只到约 **2020**，适合 Phase 0 验证链路  

## 路径 B：PostgreSQL 导出

- 脚本：`export_pg_qlib.cmd`  
- 输出：`tradeSystem/data/qlib_export/`（csv + calendars + instruments）  
- 你库里已有大量日 K / 分钟线时，应用 B 才能用「接近实盘」的数据做研究  

## Academy 控制台能做什么

- 下载官方数据  
- 预生成 `daily_pv.h5`  
- 触发 PG 导出（需本机 PostgreSQL 与 backend 配置可用）  

导出完成后，可按 `rdagent/.env` 里的 `QLIB_PROVIDER_URI` 指向对应目录（新手默认跟官方 cn_data 即可）。
