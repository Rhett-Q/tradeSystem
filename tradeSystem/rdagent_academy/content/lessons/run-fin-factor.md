# 启动与恢复 fin_factor

## 新开跑

1. 确认健康检查「可开跑」为真  
2. 在实验室 → 运行台 点击 **新开跑**  
3. 后台会调用 `scripts\rdagent_fin_factor.cmd`  
4. 日志实时刷在任务面板；产物写入 `rdagent/log/<新目录>`  

新开跑会开 **新的 log 目录**，不会覆盖旧实验。

## 恢复 / 续跑

若中途断网、LLM 报错或手动停止：

1. 打开 **Sessions**，确认最新 checkpoint  
2. 点 **恢复 fin_factor**（`rdagent_resume_factor.cmd`）  
3. 续跑会从 `__session__` 最近步骤继续，并再执行最多 `RDAGENT_MAX_LOOP` 轮  

## 费用与耐心

- 每轮都会调用 LLM，注意额度  
- 回测步骤最慢；首次构建 Docker 镜像更慢  
- 同一时间只允许一个 exclusive 任务（新开跑/恢复）  

跑完后去「读懂 Session」课，对照 feedback 学习如何判断因子好坏。
