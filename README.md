# Idea Incubation OS v2

> 代码仓 `D:\AppData\Project\Idea` ≠ 交付根 `E:\Idea`（成品交付）≠ 论文根 `E:\Paper`。
> 定位：**idea 提出辅助工具**——文献发现 → L2 全量 + idea 驱动按需 L3 → Zotero 审计入库 → Idea 交付。
> **研究者反馈（accept/reject/uncertain+理由）是唯一验证信号**；无下游实验验证是常态而非缺陷。
> 血缘：`governance/decisions.json#V2-0001`（继承科研-Idea DEC-0001~0037，v1 冻结件只读引用）。

## 快速开始

```powershell
.\os.ps1 session-brief            # canon 摘要 + runs 状态 + feedback 待办
.\os.ps1 validate --strict        # 结构校验
python -m pytest -q               # 测试
ruff check pipelines tests        # 风格
```

## 命令（`python cli.py <cmd>`，parser 为纯表面）

| 命令 | 说明 |
|---|---|
| session-brief / status / validate | 总览与门禁 |
| run-start/run-add-paper/run-prescreen/run-reconcile/run-finish/run-refreeze | 单写者 run 状态机 |
| search | 全量召回池检索（选择归会话模型） |
| claim-add | claims 中枢写入 |
| idea-add/idea-feedback/idea-feedback-stats | 候选池与唯一验证回路 |
| zotero-queue | 审计导入 manifest 队列 |

## 单写者规则（v1 P1 根因修复）

`run.json` 是唯一真源；`candidate-ledger.jsonl` 是派生视图；mechanized 预筛只写 `mechanized-prescreen.jsonl`，
经 `run-reconcile` 由同一写入器晋升。`finish` 硬门禁：L2 10–15、四路覆盖、ledger==candidates、Zotero 回读归档。
冻结统一 LF + CRLF 变体容忍；completed 改动走 `run-refreeze --reason` 审计重封。
