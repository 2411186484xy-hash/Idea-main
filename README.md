# Idea Incubation OS v2

> 代码仓 `D:\AppData\Project\Idea` ≠ 交付根 `E:\Idea`（成品交付）≠ 论文根 `E:\Paper`。
> 定位：**研究者主权的单机科研辅助工具**——文献发现 → claims 知识层 → idea 孵化与交付，止于 idea 交付。
> 认知判断归会话内模型；本地代码只做**通道、门禁、审计、状态**。研究者反馈是唯一验证信号。
> 数值单真源：`governance/workflow_authority.json`（canon，每条带 why）。架构：`docs/FOUNDATION-DESIGN.md`。

## 快速开始

```powershell
python cli.py session-brief       # 首屏：活跃 run + 知识层计数
python cli.py validate --strict   # 结构校验（冷启动应全绿）
python -m pytest -q               # 测试（stdlib-only，零依赖可跑）
```

## 命令表（21 个，README 即契约）

| 命令 | 说明 | 状态 |
|---|---|---|
| `run-start` | 启动 run（weekly/idea）；`--resume` 续跑 partial | M0 |
| `run-finish` | 收口：默认完成删除；`--partial` 留档可续；`--absorb` 放弃收口 | M0 |
| `session-brief` | 首屏四块：coverage + 活跃 run + 教训摘要 + 待办 | M1.6 |
| `validate` | 结构校验（canon 同步/悬挂 run/账本完整性）；`--strict` 警告也算失败 | M0 |
| `search` | ACTIVE 后端召回池（OpenAlex+arXiv）；`--run` 记 query_log | M0 |
| `query-brief` | 多视角查询任务包 + 查询去重 | M2a |
| `screen-rank` | 规则版排序 + 停止准则（提示性，判断归会话模型） | M0 |
| `paper-add` | 候选入 run（标识符/撤稿硬门）；`--pdf` 归档 E:\Paper | M0（--pdf 为 M2b） |
| `deepread-brief` | writer/verifier 盲分离双书任务包 | M2c |
| `pdf-extract` | PDF 文本层提取（PyMuPDF 第一通道，MinerU 探针降级） | M2c |
| `claims-add` | 追加页锚定 claim（quote 逐字 + page_anchor 硬门） | M0 |
| `claims-view` | 即席渲染（列表过滤 + 矛盾对：同 topic verdict 相反/数值冲突），不落盘 | M1.7 |
| `idea-brief` | 碰撞三要素 + 教训注入 + 6 攻击 + 查新计划（四合一） | M2f |
| `idea-add` | 供给门禁：coverage 未达阈值硬拦；过门后登记候选（M2f 完整孵化） | M1 门禁，M2f 完整 |
| `publish` | 交付 4 件套到 E:\Idea + 镜像 E:\Backup\Idea + pool 除名 | M2h |
| `feedback-add` | 研究者 verdict 回填（verdict+reason 必填，供给门输入） | M1.5 |
| `feedback-import-v1` | 回填 E:\Idea 存量 29 条 verdict（只读扫描，28 待回填） | M1.5 |
| `zotero-manifest` | 三段式第一步：manifest+SHA 暂存 | M2e |
| `zotero-write` | 窄写面：仅 manifest 批准条目 | M2e |
| `zotero-readback` | 回读审计并归档（行业空白能力） | M2e |
| `backup-verify` | 备份新鲜度检查 + 抽样恢复验证 | M2h |

## 分层（机器强制，tests/test_architecture.py）

```
L0 contracts.py   零依赖零 IO：全部记录类型 + ErrorEnvelope + trace 事件
L1 store.py       唯一磁盘 IO + 记录编解码（to_dict/from_dict，schema 门在磁盘边界）：原子写/追加 fsync/时钟可注入
L1 canon.py       canon 读取 + 四根 identity（IDEAOS_* 环境变量可重定向）
L2 search/papers/claims/idea/feedback/zotero/runs   领域模块（唯一横向依赖：runs）
L3 report/validate    纯读渲染与结构校验
L4 cli.py         纯 argparse 表面，21 命令
```

## 数据生命周期（三条根原则）

1. **做对一次**：契约 + 纪律 + 端口；靠分层与测试保持形状，不靠冻结机制。
2. **吸收即删**：run 是临时工作状态，收口即删（session-log 一行遗骸）；磁盘上只留"现在还活着的"。
3. **少即是稳**：命令 21 个、canon ≤200 行、pipelines+cli ≤4k 行、每加机制先问"V1 验证过它的价值吗"。

## 环境事实

沙箱实测 6 条见 `docs/ENVIRONMENT.md`：PS 吞 stdout / 代理假 502 / SSL certifi / MinerU 冷启动≥120s / GUI 寿命 / safe-delete；网络与证书应对已内置在 `pipelines/search.py`。
