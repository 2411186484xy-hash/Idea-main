# legacy-detours.md — V1 弯路红线（最终合并版）

> 新仓常驻纪律。来源 = 两份独立审计的合并与交叉核验：
> - **本地全量审计**（证据锚定）：`docs/V1-RETROSPECTIVE.md`（24 条弯路 + 33 条规则 + v2 现状诊断）
> - **外部扫描清单**（方法论抽象度更高，覆盖面更广）
>
> 合并原则：保留两边的**全部**条目，去重后按"红线规则"重组；每条后括注 V1 的伤疤作为证据。
> 与 `V1-RETROSPECTIVE.md` 的分工：那份是**证据档案**（按弯路组织，可考古），这份是**纪律清单**（按规则组织，可照做）。

---

## 0. 核验声明（对方清单中被修正的数字）

审计要求"事实先行"。对方清单的方向与结论基本可靠，以下数字经实测修正：

| 对方表述 | 实测结果 | 处理 |
|---|---|---|
| "老仓 7GB 仓库" | 仓库本体（工作树 + `.git`）≈ **1.4 GB**；加上环境 `.venv` **1.4 G** + `.venv-mineru` **4.6 G** ≈ **7.4 GB** | 数字成立，但须区分"仓库"与"环境"——**代码仓是 1.4 GB，环境是 6 GB** |
| "`literature_search_tools.py` 曾 2367 行" | 峰值 **2396 行**（`1b8d686`），当前 2342 行 | 修正为 2396 |
| "`oc_research_os.py` 曾 3000+ 行" | 峰值 **9576 行**（`034440c`，08-25）；轨迹 3975→8793→**9576**→8175→6726→626→378→216 | **严重低估**，修正 |
| "marketplace v0.4.0" | 确证：`git show 85dbd9d^:tools/marketplace.json` → `"version": "0.4.0"`，含 10 个 skill，`install: hermes skills trust .` | 采用 |
| "34 idea 只 7 条失败" | 确证：`idea_failure_ledger.json` → `entries` 长度 = **7** | 采用 |
| "8-item high-star / 32 仓 borrow 一周内建一周内埋" | 实测落地→删除间隔为 **11–19 天**；但有极端案例 `cli_*.py` **仅 2 天**（`7be3709` 09-03 → `52c254d` 09-05） | 修正为 **2–19 天** |
| "deprecated 三天后" | 未找到佐证 | 不采用 |
| "6 个零消费 .py" | **2 个零消费**（`tools/arxiv_html_meta.py`、`tools/claims_append.py`，仅被 `decisions.json` 提及）+ **4 个半孤儿**（`idea_collision.py`/`idea_rubric_loop.py`/`skill_distill.py`/`papers.py` 无 CLI 接线） | 修正为"2 零消费 + 4 半孤儿" |
| "run.json 已有 17 候选 / 19 深读而 report.md 空白" | **未能复现该组合**；但同类问题**已确证**（见 B-2 的账本断裂实测表） | 该具体表述不采用，问题本身成立 |
| "equilibrium 六维 4.5/5" | 确证：`outputs/archive/reviews-202609/equilibrium-dashboard.html` 含 `4.5/5` | 采用 |
| "9-14 batch 完 → 9-19 迁移 → 9-20 又 true rebuild" | 确证：`1b8d686`(09-14) → `92a2542`(09-19) → `4f99e31`(09-20) | 采用 |
| "TEST-* 109 周索引 + 135 历史条目" | 确证：`a378a17` | 采用 |
| "RUN_RESEAL 6 个 run" | 确证：`state.json` history 中 `RUN_RESEAL` 6 次、`RUN_REFREEZE` 9 次 | 采用 |

---

## 1. 第一天不变式（先立这 12 条，其余都是推论）

| # | 不变式 | 违反后的样子（V1 实例） |
|---|---|---|
| 1 | 一个 canon 文件，无镜像/无指针层 | 双源漂移、5 轮 shim 化 |
| 2 | 每个策略值只有一个机器可读来源，且断言无副本 | 90min×3、集合名×13、L2 配额双写 |
| 3 | 每个状态文件只有一个写入者，且有对账通道 | `cand=14/ledger=0` 的账本断裂 |
| 4 | 冻结前归一字节，冻结后任何人只读不动 | 30 天、约 18 次重冻结 |
| 5 | 所有输出根走环境变量，测试默认重定向 | 8 次写穿真实仓库、2395 文件 |
| 6 | 只有证据充分性可以当硬门禁 | 全量 L3 硬门 → 达成 3/12 → 被迫废除 |
| 7 | 门禁自身必须有测试 | `validate --strict` 自己坏了 |
| 8 | 反馈覆盖率是第一屏数字，且低覆盖时禁止扩大供给 | 40 slug vs 1-2/周 champion |
| 9 | 认知决策在会话内做，自动化只管机械步骤 | 无人值守周任务建 9 次后删除 |
| 10 | 产物/缓存/备份不进版本库 | 2774 PNG = 70% tracked 文件 |
| 11 | git 先于一切；结构性改动走分支 | 130 commit 全在 master，无隔离 |
| 12 | 外部能力 borrow-not-merge，过端到端验收 | docling 验收 = `--help OK` |

---

## 2. 红线全录（九组）

### A. 单一真源

- **A1 规则只活在一处，其余是指针。** 禁止 canon + AGENTS + prompt + contract 多份并存。V1 为这一件事做了 5 轮（`9cf92e7`→`f36d814`→`051e1a4`「anti-oscillation endgame」→`34fc4ba`→`79825bc`→`59456d4`），AGENTS.md 被改 26 次、canon 33 次。
- **A2 锁要锁内容哈希，不是 mtime。** `skills-lock.json` v1 只记 mtime + `version: unknown`，自己就在漂移。
- **A3 数值留在数据，代码只当解释器。** 领域本体（阈值、配额、枚举、模板项数）进 canon；代码只读取。
- **A4 规则组织形式不要反复震荡，第一天定死。** contract→canon 上收→canon 拆分→又回单源，是纯粹的空转。
- **A5 同类配置只声明一处。** 依赖 / CI / pre-commit 三处版本各管各的（本地 ruff 0.16.3 全绿，CI 与 pre-commit pin 0.15.14——**本地通过 ≠ CI 通过，靠运气**）。
- **A6 禁止落盘快照作为后续依据。** V1 的 layout 快照与实况漂移（`zotero_exports` 实测 11 vs 快照 171；`outputs` 71 vs 7）；快照必然腐烂成假规则。上下文一律实时生成。

### B. 状态与账本一致性

- **B1 每个状态文件只有一个写者。** 派生视图（ledger、矩阵、brief）一律由单一源重建，禁止人手写状态键。V1 的 P1 根因就是 `mechanized_retrieval` 与 `run-add-paper` 双写同一 ledger 且无对账通道 → `run-finish` 的 `ledger==candidates` 硬门永久 blocked，只靠一次人工 `STATE_LEDGER_RECONCILE` 兜底。
- **B2 账本与 run.json 必须一致，且要有内置对账命令。** 实测账本断裂（V1 现存）：
  `WEEKLYRUN-20260814-094518` → cand=14 / ledger=**0**；`WEEKLYRUN-20260902-104920` → cand=15 / ledger=**0**；`WEEKLYRUN-20260818-134225`（等 5 个）→ cand=0 / ledger=**1**。
  V2 的 `reconcile()` 已对，但**仍缺一个"一致性体检"命令**扫描全部 run 报出此类断裂。
- **B3 字段建了就要流转，否则是空转。** V1 候选池长期无 verdict/评分字段；`zotero_membership_plan`/`decisions_requested` 全程 **0 条流转**。
- **B4 先写盘全部工件，再算哈希冻结。** V1 的 freeze 时序 bug（先算哈希、后写 report/run.json）→ 每次收口假警报。
- **B5 失败账本必须如实记。** V1 存量约 34 个交付 slug，`idea_failure_ledger.json` 只有 **7 条 entries**；没有失败样本，反模式卡就无从生长。
- **B6 不留悬挂 active run，要有超时收口。** V1 有 `WEEKLYRUN-20260913-151819`（cand=16/ledger=16/**seeds=0**，未收口）、`_quarantine-20260903-empty66`（66 个空 run 的重试风暴）、3 个 stale active idea run。**V2 第一天就出现了 `WEEKLYRUN-20260920-120000`。**
- **B7 "实物产出跑在记账前面"是病征。** 写盘与记账必须同源同步。

### C. 门禁与"治理自指"

- **C1 门禁不能自身有 bug。** V1 的 `validate --strict` 对最新 run 硬失败（"freeze 时序 bug"）——**门禁可信度受损比没有门禁更糟**。
- **C2 达标不能自证，必须有外部可验证的产出证据。** V1 的 equilibrium 自评"六维 **4.5/5**"（`equilibrium-dashboard.html`），靠的是"模板存在"，被审计当场戳穿：L3 深读 **3/12** run、34 个交付 slug 仅 **2** 个含完整交付物。
- **C3 禁止静默吞异常。** V1 约 **95 处** `except Exception: pass` —— 形成"降级文化，故障不可观测"。改用显式异常或结构化降级记录。
- **C4 门禁要少而硬，且每条都能被豁免 + 留痕。** 禁止"卡死无法收口"（V1 被迫给 seeds 硬门加 `--supply-hold-reason`）。
- **C5 配额类 / 覆盖率类 / 日历类不得设为硬门。** V1 的 L3 固定配额、coverage 百分比、JCR Q2 硬门全部被软化（hard↔soft 摆动 5 次）——**凡是被反复软化的门禁，说明它本来就设错了**。
- **C6 每加一层质量机制，必须同时冻结或废掉一层（总量封顶）。** V1 深读质量层 **6 轮叠加、从未下线一层**：depth-v2 / v3 / v3.1 三代协议并存，claims/facts/matrix/gap-map 四套视图，`cold_recall.py` 零产物。实际只有 **10 篇** `verified_l3`。
- **C7 外部工具闸门只能 soft trigger，不得在运行中悄悄升级为硬门。** V1 的 JCR 曾从 hard 静默转 `soft_reference_only`（`776f37f`），此前已按 hard 卡过产出。
- **C8 门禁的核心语义不能在 canon 内自相矛盾。** V1 主文件同时存在"全部 10-15 hard / 不按固定配额 / 已置 none"三种 L3 说法（`:263` / `:700` / `:992` / `:1095`）。

### D. 范围与欠债（防 build→prune）

- **D1 新能力/新依赖过"立项门禁"，无真实需求不引入。** V1 的 docling（18 天后删）、qdrant（从未安装，每次初始化打 WARN）、Minera（4.6 GB 环境养废）。
- **D2 对标外部做堆料 = 高危动作。** V1 在 09-02 ~ 09-03 一口气落地 8-item high-star + 32 仓 borrow + marketplace v0.4.0（10 skill），**2–19 天**后批量删除（`52c254d`/`7c677ca`/`85dbd9d`/`f287d32`/`14ac969`）。**建得越快，埋得越快。**
- **D3 scope 边界钉死，不事后扩张。** V1 下游仓单仓 → A/B/C 三仓 → 双活 → 再归一；边界反复拆合是定位没想透。
- **D4 borrow-not-merge，重依赖禁止混入。** 只走"数据替换 / 薄适配 / 设计借鉴"三档；AGPL/GPL/NOASSERTION/无许可一律禁。
- **D5 build→prune 循环要有止损锚点。** V1 的锚点漂了三次：09-14 batch 收口 → 09-19 迁移 → **09-20 又 true rebuild**。须明确定义"发布/稳态"信号。
- **D6 新功能必须先在真实 run 上被验证才能入库。**
- **D7 不许"建了几天就推翻"。** V1 极端案例：`tools/cli_*.py` 五个文件 09-03 建、09-05 删（**2 天**），作者自述"only referenced by their own guard tests"。
- **D8 never-landed 直接删，不归档。** V1 反复"先归档、后删除"：`_legacy_archive/`（含 `research_os.py` 7413 行）8 天后删、`_deprecated_archive/` 11 天后删。git 已是历史，不需要第二份。**唯一例外：研究者原始输入（论文、标定数据）。**

### E. 环境与可重建

- **E1 环境远离代码，一条命令可重建。** V1 总占用 ≈ 7.4 GB，其中 **6 GB 是环境**（`.venv` 1.4 G + `.venv-mineru` 4.6 G）——对"平替"而言等于不可迁移。
- **E2 路径常量化，禁盘符 / 个人目录 / 代理 / 邮箱字面量进 commit。** V1 tools 层 **43 处**盘符字面量；换机（D/C 盘 → E 盘）触发两天大规模返工，`.venv-mineru` 锚定旧机用户路径、`RESEARCHER_SCAN_ROOT` 指向不存在目录**静默空转**。
- **E3 外部根名用唯一常量 + 回归门禁。** V1 父集合改名暴露 **13 处**硬编码，最坏情形 `zotero_cmds.py:737` 会**静默新建一个空集合、数据进错地方且无报错**。
- **E4 写通道/权限边界如实承认，不冒充能替代人工。** V1 的 Zotero 写必须经研究者本机 UI 会话（pywinauto + 可见主窗口），自动化只能"生成 manifest → 人工执行 → 回读校验"。**不要把审计层再做成额外人工卡点。**
- **E5 SSL/证书走代码级兜底，不依赖用户级环境变量。** 用户级 `SSL_CERT_FILE` 对已启动会话失效，且 venv 重建后成陈旧指针。V1 实测：该变量已从 `HKCU\Environment` 删除，**不要写回去**。
- **E6 迁移先 dry-run / diff，再执行。** 不做盲迁移。
- **E7 冻结工件不可改；source provenance 不重写。** 需要合法补写时走审计式 refreeze（reason 必填 + 落 history）。

### F. 反馈与验证回路（治本）

- **F1 唯一验证信号必须真实闭合。** V1 把研究者反馈定为唯一验证信号，结果：`idea-feedback.jsonl` **不存在**、29/29 `researcher-decision.json` 的 verdict **全部缺失**、`state.history` **0 条** `IDEA_FEEDBACK`——**却在继续给系统加功能**。这是 V1 最狠的一戒。
- **F2 反馈优先于新供给。** 先回填存量 verdict，再产新 idea。
- **F3 reject 必记失败账本，且要能反哺下一次生成。**
- **F4 认知判断交给模型，但必须落成不可变、可被独立 verifier 复核的 artifact。** 不能留在空气里；也不要为此写 13k 行的临建工具——需要一个干净接缝。
- **F5 深读由 idea 驱动，不"找到就读"。** V1 的"找到论文就深读"（DEC-0006）被废除过两次。
- **F6 不承诺"全量"，只承诺"按需"。** V1 的"每周 10-15 篇全量 L3"是最大的返工源：DEC-0006 → 0018 → 0019 → 0023（被迫降级）→ 0035（废除配额）。

### G. 工程细节

- **G1 统一写入器**：UTF-8 / LF / 尾换行 / 固定排序。V1 的 `RUN_RESEAL` 6 个 run 全是字节漂移受害者。
- **G2 哈希规范化范式一次定死，不演进。** V1 的 parity 曾死循环（11 次 manifest 重写）。
- **G3 改字节的钩子必须 `exclude` 冻结目录。** `end-of-file-fixer` / `trailing-whitespace` / `ruff-format` 与冻结哈希正面冲突，V1 只能整片豁免 `runs/`，并被迫接受 CRLF/LF 多变体（**削弱了篡改证据本身**）。
- **G4 测试必须隔离写 + 仓库污染守卫。** V1 污染 **8 次**：`758ba1d` 一次清 **2395** 文件，`a378a17` 清 244 条 state 残留，测试残壳还落进过 `E:/Idea` 交付根。有效方案 = 会话首尾 `git status --porcelain` 对比 + 全部输出根环境变量化 + legacy 路径哨兵。
- **G5 从一开始就小模块。** V1 的 `oc_research_os.py` 10 天从 3975 → **9576** 行（超自定 8500 行上限 1000+ 行，规则先失效后追认）；最终靠 4–5 次 god-split 才降到 216 行。`literature_search_tools.py` 峰值 **2396** 行。
- **G6 孤儿模块 / 孤儿目录随时清。** V1 现存 2 个零消费模块 + 4 个半孤儿。
- **G7 CLI / 控制面不要并行双套。** V1 老脚本入口与 `oc_research_os` 控制面并行存在过，后来删一套。
- **G8 生成/交付物要进持续门禁。** "跑通一次"等于没闭环。

### H. 顺序与节奏

- **H1 先收敛存量，再铺新供给。** 不做"一边堆库存一边开新线"——V1 的 40 slug 存量 vs 每周 1–2 champion 名额，最终被迫给供给侧装减速阀，还要为减速期给 seeds 硬门打豁免补丁。
- **H2 不要用新机制治旧机制的副作用。** V1 为治"冻结漂移"加了 parity 机器，机器又成新负担，最后整包删除（`34fc4ba`）——**该修的是写入器**。
- **H3 无分支隔离 = 直接在线改生产。** V1 的 130 个 commit **全部在 master**，无 feature branch、无 stash。

### I. 认知与自动化的边界

- **I1 认知决策永远在会话内做，自动化只管确定的机械步骤。** V1 的无人值守执念：Windows 计划任务 → Hermes cron → 全废改对话驱动（`weekly-research-schedule.ps1` 改 9 次后删除）；本地小模型（qwen/Ollama/paper-ask）退出质量链。**不要用机械调度替代最贵的认知环节。**
- **I2 规则总量应与真实决策数成正比，而不是与焦虑成正比。** V1 自评："这个系统当前最大的敌人不是外部检索质量，而是自身的复杂度维护成本。"
- **I3 每份报告必须绑定一个已执行的改动。** V1 一次性归档约 28 份评审/对标文档，README 自评"未随代码演进更新"。**写而不用 = 负债。**

---

## 3. V2 现状：已复发与未覆盖

### 3.1 已正确吸收（12 条）

单写者状态机 + 侧账 + reconcile（`runs.py`）· LF 归一 + CRLF 容忍冻结（`common.py:64`）· 审计式 refreeze（`runs.py:231`）· 空 run 守卫（`runs.py:48`）· seeds 减速期豁免（`runs.py:195`）· canon 单真源 + identity 断言（`canon.py:27`）· permissions 真执行 + 双向无孤儿审计（`permissions.py:46`）· 交付 core-4 分层（`idea.py:117`）· 反馈回路 CLI（`idea.py:63`）· 产物不入库（`.gitignore`）· 核心依赖仅 3 个（`pyproject.toml`）· 反模式卡继承。

### 3.2 已复发（10 条，写业务代码前必须修）

| 对应红线 | V2 位置 | 现状 |
|---|---|---|
| **A2/A3** | `runs.py:21`（`L2_MIN, L2_MAX = 10, 15`）、`idea.py:15/26`（`QUALITY_DIMS`、`need={3,1,1}`）、`papers.py:10`（`L3_PATHS`）、`idea.py:117`（`CORE_FILES`） | **策略数值双写 5 处**；canon 里全有同名定义，而 `canon.check_identity_sync()` **只校验 Zotero 两项** |
| **C8** | `runs.py:20` vs `literature.py:14` | **路由枚举两套且不兼容**：`counter_boundary` vs `counter`/`boundary`——按后者填表会被 `add_paper` 直接拒（**现存 bug**） |
| **B6** | `runs/weekly/WEEKLYRUN-20260920-120000/` | 悬挂空 active run |
| **G6** | `runs.py:267-268`（`void = ...; _ = void`）、`validate.py:68-69`（空操作）、`pipelines/papers.py`（无 CLI 入口）、`delivery/`、`integrations/`（空目录）、`__pycache__`（cpython-310 + 314 双份） | 死代码与半成品痕迹 |
| **G4** | `tests/conftest.py` **仅 4 行** | 无污染守卫；隔离靠手写 `monkeypatch` 打 8 个路径常量——漏一个就写穿真实仓库 |
| **G11（第一天不变式）** | 无 `.git`、无 `.github/`、无 `.pre-commit-config.yaml` | **最严重**；且 G4 的守卫依赖 git |
| **E1/E2** | `common.py:22-25` + canon `identity` | 绝对路径仍进仓（已集中，但 `check_identity_sync` 不校验路径） |
| **C4/E4** | `permissions.py:37-38` | `allow_with_recent_backup` 是**假严格**：直接放行 + 注释"由 caller 校验"，但没有 caller |
| **C5/C6/F6** | canon `week_modes`(2:2 自适应)、`parallel`(6/5/4/4/5)、`runs.finish_gates.l2_quota`(hard)、`deep_read.templates`(v3 模板) | **搬回了 V1 已证伪的机制**——这些数值正是 V1 调参后 OOM、被去周化、被废除配额的那一组 |
| **G7/A5** | `pyproject.toml` 保留 `vector` extra(chromadb)；`claims.record_verdict` 全量重写 vs `append_claim` 追加；`validate.REFERENCED_ACTIONS` 手工维护 | 休眠依赖 + 同文件两种写模式 + 元数据手工同步 |

### 3.3 尚未覆盖（6 条）

版本控制 + CI + pre-commit（红线 G11）· 仓库污染守卫（G4）· 备份机制与前置校验（对应 V2 `permissions.json` 里那条无实现的策略）· 存量反馈消化机制（F1/F2，V2 的 pool 为空，机制无处落地）· 交付卫生检查（对应 V1 DEC-0032 三条规则）· 文档腐烂防护（I3）。

---

## 4. 收官

> **别让系统越来越擅长"看起来正确"，而要让产出的证据能被外部核查。**

V1 约 95% 的弯路都收束在这一句里：无人值守执念、堆料对标、门禁自证、多份真源、反馈空转、无限重写——**全是它在追求"治理上无懈可击"，而不是"研究产出可验证"。**

新仓唯一的护身符，是第一关先跑出一个**带 verdict + 真实研究者反馈**的 idea。跑出来，就赢过了 V1 整个治理层。

---

*配套文档：`docs/V1-RETROSPECTIVE.md`（证据档案）、`docs/V2-ACTION-ITEMS.md`（可勾选整改清单）。*
