# RD-Agent 是什么

**RD-Agent**（Research & Development Agent）是微软开源的自动化研发智能体。在量化场景里，它能自动完成：

1. 提出因子假设  
2. 写出因子代码  
3. 在 **Qlib** 环境里回测  
4. 根据结果决定是否采纳，并进入下一轮演化  

你可以把它理解成：**会写代码、会跑回测、会写实验笔记的研究助理**。

## 它解决什么痛点

传统因子研究要人手写假设、实现、回测、复盘。RD-Agent 把这条链路串成可重复的 **Loop**，适合：

- 想快速探索大量因子想法  
- 希望把「LLM 写代码」和「严格回测」绑在一起  
- 作为 TradeSystem 的**研究轨**，与生产选股/回测并行  

## 在本仓库里的位置

```
tradeSystem/
├── backend/          ← 生产轨：PG + 自研因子 / 回测 API
├── rdagent/          ← 研究轨：独立 Python 3.11 venv + Docker Qlib
├── scripts/rdagent_* ← 一键脚本（健康检查、下载数据、fin_factor…）
└── rdagent_academy/  ← 本学习站（你正在用）
```

## 下一步

先读「生产轨 vs 研究轨」，搞清两套系统不要混用环境；然后做环境检查，确认 Docker 与数据就绪后再开跑。
