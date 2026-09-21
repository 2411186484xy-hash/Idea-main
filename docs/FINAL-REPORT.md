# V1 弯路审计与新仓设计依据 · 最终报告

| | |
|---|---|
| **审计对象** | `D:\AppData\Opencode\Project\科研-Idea`（下称 **V1**），41 天 / 130 commit / 2026-08-11 → 2026-09-20 |
| **目标仓** | `D:\AppData\Project\Idea`（下称 **V2**），2026-09-20 16:25 建仓，1615 行骨架 |
| **报告性质** | 本报告为**单一入口的最终版**，整合三份过程产物（见附录 A） |
| **标注约定** | **（已验证）** = 有命令输出 / 文件内容 / commit 佐证；**（未证实）** = 仅有间接线索，不采用 |
| **V2 状态快照** | 2026-09-20 23:11 核验：**尚未整改**（无 `.git`、悬挂 run 仍在、5 处数值双写仍在） |

---

## 摘要

V1 不是"写坏了"，而是**六周内把治理、工程、业务三条线各自都做成了自我维护的负担**。它自己的诊断最准确：

> 「总评：6.3 / 10 —— 设计成熟（A-），执行落差（C+）」——`outputs/project-audit-2026-09-05.md`
> 「这个系统当前最大的敌人不是外部检索质量，而是自身的复杂度维护成本。」——`outputs/project-objective-review-20260905.md`
> 「下一阶段的主要矛盾已从"建成管道"变为"给系统减重"。」——同上 r2

**量化结果（即"捷径没走通"的证明）**：

| 指标 | 结果 |
|---|---|
| 声明的核心环节 L3 深读 | 3/12 run 达成；真正 `verified_l3` 仅 **10 篇**（`reading_state.json` 90 条） |
| 13 件交付完整度 | 2/34 |
| 唯一验证信号（研究者反馈） | **0 条记录**，29/29 verdict 缺失 |
| 检索通道净产出 | 引入约 14 个 → 现役 **3 个** |
| 供给 vs 消化 | 40 个 idea slug vs 每周 1–2 个 champion 名额 |
| 冻结哈希重冻结次数 | 约 **18 次**，跨 30 天；单 run 极值 `refreeze_count=6` |
| 测试写穿真实仓库 | **8 次**，`758ba1d` 一次清 2395 文件 |
| 静默吞异常 | 约 **95 处** `except Exception: pass` |

**如果只做六件事**（P0）：

1. `git init` —— V1 最有价值的资产就是那 130 个 commit
2. 删悬挂 active run `runs/weekly/WEEKLYRUN-20260920-120000`
3. 修 **5 处策略数值双写**（`runs.py:21`、`idea.py:15/26/117`、`papers.py:10`）
4. 修 **路由枚举矛盾**（`runs.COVERAGE_ROUTES` vs `literature.DISCOVERY_CLASSES`）
5. 补**测试隔离 + 仓库污染守卫**（现 `tests/conftest.py` 仅 4 行）
6. 删死代码（`runs.py:267-268`、`validate.py:68-69`）

**核心原则**：凡是 V1 用"再加一层机制"解决的问题，V2 一律改用"删掉问题的来源"。

---

## 1. 审计范围与方法

### 1.1 覆盖面

| 维度 | 覆盖 |
|---|---|
| git 历史 | 130 个 commit **全量 message**（含正文）、`--diff-filter=D` 删除清单、`--stat` 抽查 |
| 治理 | 37 条 DEC 全文、1145 行 canon 全文、`AGENTS.md`、`permissions.json`、各 contract |
| 自审文档 | `outputs/` 全部 11 份审计/复盘报告 + `outputs/archive/` 约 28 份 |
| 归档 | `work/.archive/` 全部 30 个子项 |
| 代码 | V1 现行 `tools/`（55 个 .py）+ `tests/`（191 个测试）+ 依赖清单 |
| V2 | 全部代码 1615 行 + governance + tests |

### 1.2 三种取证方式

- **git 考古**：从 fix/revert/refactor/purge 类提交统计"同一问题被修几次、跨多少天"
- **文档考古**：V1 自己的审计报告与归档目录（最诚实的第一手材料）
- **代码考古**：现行实现里残留的死代码、双源、孤儿模块、可再生成物

### 1.3 结论的组织方式

弯路按**域**记录（第五部分，24 条，可考古）；经验按**规则**组织（第四部分，52 条，可照做）。

---

## 2. V1 事实基线

| 维度 | 实测值 |
|---|---|
| 提交 / 跨度 | 130 commits / 2026-08-11 → 2026-09-20（41 天） |
| 分支 | **仅 `master`**，无 feature branch、无 stash |
| 仓库本体 | ≈ **1.4 GB**（工作树 + `.git` 420 MB） |
| 环境占用 | ≈ **6 GB**（`.venv` **1.4 G** + `.venv-mineru` **4.6 G**），合计 ≈ **7.4 GB** |
| 曾入库的可再生成图 | 2774 张 PNG ≈ 当时 tracked 文件的 **70%** |
| canon | 1145 行 / 75 KB，被改 **33 次** |
| `AGENTS.md` | 被改 **26 次**（325 行 → 44 行 → 又长回 15 KB） |
| 决策 | **37 条** DEC |
| 工具链 | 75 个 CLI 子命令；`tools/` 23959 行；191 个测试 |
| 依赖 | 核心 6 个；`uv.lock` **1.03 MB** / 172 packages（曾 8 KB → 1.21 MB） |
| 神文件峰值 | `oc_research_os.py` **9576 行**；`literature_search_tools.py` **2396 行** |
| run 收口 | 24 个 weekly run 中 5 completed / 19 partial |

---

## 3. 弯路全录（24 条）

> 本节为总纲，每条给出「现象 → 证据 → 根因 → 代价 → 规则」。逐条完整证据链见 `docs/V1-RETROSPECTIVE.md`。

### A. 治理域（5 条）

**A1 规则多副本 → "真 shim 化"反复 5 轮**
同一规则同时存在于 `AGENTS.md` / `coordination/*_prompt.md` / `*_contract.json` / `canon` 四处，每次改动产生漂移。
证据：`9cf92e7` → `f36d814` → `051e1a4`（标题 `anti-oscillation endgame`）→ `34fc4ba` → `79825bc` → `59456d4`，跨 14 天。
根因：把"单一真源"当成要靠机制维护的属性（shim 体积断言、悬空锚点断言），而不是**物理上只有一个文件**。
代价：7 个 commit 的治理空转；直到 09-05 仍在删 canon 死副本。
→ **只允许一个 canon 文件。禁止 shim / 镜像 / 指针层。**

**A2 策略值散落硬编码**
证据：90min 上限被删 **3 次**（`3e55930`/`a64484f`/`2938d6f`，同日）；Zotero 集合根名 **13 处**硬编码，`72b4505` 原文「worst case `zotero_cmds.py:737` *created* a fresh empty "opencode" root when the lookup missed」——**静默新建空集合、数据进错地方且无报错**；神文件自定 8500 行上限但涨到 9576 行，规则先失效后追认。
根因：没有"副本检测"这个动作——规则只在人脑，不在 CI。
→ **每个策略值只有一个机器可读来源，且用测试断言无副本。**

**A3 canon 双源 + 快照腐烂**
证据：DEC-0028 把 canon 拆成 `canon/*.json` 分片 → 5 天后 DEC-0031 又删（"零消费方且与主文件漂移"）；`project-objective-review-20260905-r2.md`「**快照腐烂** … 上下文注入层在消耗过期信息」（`zotero_exports` 实测 11 vs 快照 171）。
根因：任何"某时刻复制过来"的快照都会腐烂。V1 自己在 `AGENTS.md:33` 写下了这条，又自己违反。
→ **上下文注入只允许实时生成，禁止落盘快照作为后续依据。**

**A4 门禁多而软、反复软化**
证据：canon 声明 **14 个 gate 键**，18 处 `hard` / 17 处 `warn` / 8 处 `soft`；hard↔soft **摆动 5 次**（`9cf92e7` 放松 → `3e55930` 收紧 → `051e1a4` 对半 → `8692b05` 再收紧 → `776f37f` 再放松 → DEC-0035 废配额 → DEC-0037 加豁免）。canon 内部自相矛盾：同一 L3 门禁有"全部 10-15 hard / 不按固定配额 / 已置 none"三种说法（`:263`/`:700`/`:992`/`:1095`）。
根因：门禁被当成"表达焦虑"的工具，而不是"表达约束"的工具。
→ **凡是被反复软化的门禁，说明它本来就设错了。**

**A5 声明超前于实现**
证据：`zotero_proxy_guide.md §6` 宣称"5-channel fanout + 第 6 个 Lens 通道"——实际 3 个源，Lens 从未实现（`0d1fb06` 专门纠错）；`.env` 的 `LENS_API_KEY`/`NCBI_API_KEY` 全仓无消费方；canon 被迫写「**声明不超前于实现**」。
→ **文档只写代码实测存在的能力；新增 canon 规则必须同时落一个能失败的测试。**

### B. 工程域（7 条）

**B1 冻结哈希 × 改字节钩子对撞（最严重，30 天）**
`end-of-file-fixer` / `trailing-whitespace` / `ruff-format` 与 `frozen_hashes` 形成机制级死锁：冻结 → 提交 → 钩子改字节 → 哈希失效 → 人工重冻结。
证据：`parity_manifest.json` 被 **33 次** commit 触达；`e2d7cb4` 自称"根治"（原文 `Root fix for the historical freeze→commit→hook-normalize→re-freeze loop (11 manifest rewrites)`）后仍继续重冻结（`473f381`/`318f162`/`efa8faf`/`bd88f83`/`e5843d7`）；单 run `refreeze_count=6`；最终**整包删除机制**（`34fc4ba`）。
残留成本：只能整片 `exclude: ^oc-research-os/runs/`，并让哈希函数接受 CRLF/LF/有无尾换行多变体——**削弱了篡改证据本身**。
→ **字节归一化只能发生在冻结之前，且是唯一入口；冻结后禁止任何进程改写。**

**B2 同一"防漂移"机制重复造三遍**
`frozen_hashes`（run）/ `parity_manifest`（contract）/ `skills-lock`（skill）同型；`skills-lock.json:5` 自述 v1「只记 mtime + `version:'unknown'`，无法检测 skill 内容漂移」。
→ **一个内容哈希原语 + 一处实现。**

**B3 测试污染真实仓库（跨 26 天、8 次）**
证据：`758ba1d` 一次清 **2395** 文件（145 IDEARUN + 164 RECOG + 135 fixture）；`a378a17` 清 **244 条** state 残留；`fb5e56e` 曾写穿真实 `reports/eval-2026-09-05.json`；09-13 测试残壳落进真实交付根 `E:/Idea/`（`C1`/`conformal`/`sensor-informed`/`title-c1`）。
成因（`conftest.py` 自述）：生产命令直接写 `oc-research-os/`；`IDEA_DELIVERY_ROOT` 在 Linux CI 上变相对路径，跑出仓库内的 `D:/...` 树。
→ **测试默认隔离到 tmp + 会话首尾 `git status` 污染守卫 + 输出根全部环境变量化。**

**B4 可再生成物入库**
证据：`.gitignore:67-70` 自述「2774 pngs were ~70% of tracked files and the main .git bloat driver」；清理 commit `eea05ea` 原文「removed from index only … **History rewrite deferred**」→ 2285 个 png blob / 68 MB **永久留在 `.git`**；单文件级 `RECOG-20260831-112239/run.json` 1.52 MB；仓库内自我备份 zip 209 MB。
→ **crops / PDF / 缓存 / 备份一律不进版本库。**

**B5 无真锁的状态写**
`load_state`/`save_state` 无锁、无 CAS；`acquire_lock` 是 **mtime 陈旧锁**（600s 提示，非互斥），且全仓只有 backup 一处调用。
→ **单机单进程场景不引入锁（V1 证明它是装饰品），改为"每个文件只有一个写入者"的结构性保证。**

**B6 自建宿主已提供的能力**
`tools/skill_registry.py`(118 行) + `agent_orchestrator.py`(257 行) + `tools/skills/`（11 包）+ `tool_manifest.yaml` + `marketplace.json`（v0.4.0，10 skill）——2026-09-13 仍在扩张，**2026-09-14 `85dbd9d` 整批删除**（30 files, +5/−683，理由"canon/CLI 零引用"）；最后一个 skill 包存活 **1 天**。
→ **引入任何子系统前，先写一句"宿主为什么不能做"。**

**B7 死件与"从未落地"的能力**
证据：`docling` 18 天后删，`14ac969` 原文「historical acceptance was literally "--help OK + dummy PDF extracted 0 tables / 0 formulas". The table-formula channel never worked.」；`qdrant-client` 从未安装（每次初始化打 WARN 后回落）；现存 **2 个零消费模块**（`arxiv_html_meta.py`/`claims_append.py`）+ **4 个半孤儿**；`_legacy_archive/`（含 `research_os.py` 7413 行）归档 8 天后删；`cli_*.py` 5 文件 **2 天**推翻。
→ **never-landed 直接删，不归档；验收标准是端到端产出正确结果。**

### C. 业务域（5 条）

**C1 承诺"全量 L3" → 深度稀释 → 反复降级**
证据：`8692b05` 定 `10-15 all hard` → DEC-0023 降为"10-15 L2 卡 + 3-5 篇 L3" → DEC-0035 **废除配额**。结果 `verified_l3` 仅 **10 篇**。
深读质量层 **6 轮叠加、从未下线一层**：depth-v2 / v3 / v3.1 三代协议并存，`cold_recall.py` 零产物，`Consistency-Check` 仅 47/151 篇。
→ **先用最小深读跑满，再谈加层；每加一层必须冻结或废掉一层。**

**C2 供给过剩 → 被迫装减速阀**
证据：「40 个 idea slug vs 每周仅 1-2 个 champion 名额」（`project-objective-review`）；「27 已交付中，可作为毕业路径的仅 3 簇 4 个」（`condensed-review-20260831.md`）→ DEC-0033 加 `supply_policy` 降频 → DEC-0037 又给 seeds 硬门打豁免补丁。
→ **没有消化管道的生成器只会生产债务。**

**C3 反馈回路"建了不用"**
证据（2026-09-20 实测）：`idea-feedback.jsonl` **不存在**；29 份 `researcher-decision.json` 的 verdict **29/29 缺失**；`candidate-pool.json` 含 verdict 的文件数 **0**；`state.history` **0 条** `IDEA_FEEDBACK`。
→ **反馈覆盖率必须是首屏数字；coverage 低时禁止扩大供给。**

**C4 检索通道铺开 14 个 → 现役 3 个**
存活：OpenAlex（主源，有限流纪律）、Crossref（补源）、arXiv 直连（`387053c`，修的是"arXiv 索引腐败"**误诊**——实为 MCP 瞬时故障）；保留 Europe PMC；退役 semantic-scholar MCP / paperscraper（降级）/ Lens（**key 401，从未实现**）/ pubmed_search（先实现后删）/ OpenReview（100% DNS 失败）/ Tavily（无 key 休眠）/ zju-literature-downloader + `zju_fetch.py`（**18 天后退役**，依赖研究者本机 Chrome 登录 + CDP proxy + WebVPN）。
→ **只保留能自动、无人值守、端到端产出的通道。**

**C5 Zotero 链路被迫绕**
约束来源判定：**API 只读（外部强加）** + 不碰 SQLite（自加安全取舍）+ manifest/sha256/readback/7天备份前置（自加审计）+ **硬编码 13 处、import_queue 双位置、membership JS 缺 `.id`（自己造成的 bug）**。
→ **接受"Zotero 是半自动通道"，设计成三段式显式流程；不要把审计层再做成额外人工卡点。**

### D. 环境与路径域（3 条）

**D1 绝对路径硬编码（跨 36 天）**
证据：`2903b23`（08-15）第一次 `fix absolute path refs`；`92a2542` 迁移时「the repo was cloned from another machine whose roots … no longer exist」；迁移清单定位 **代码层 10+ 文件、配置/治理层 14+ 文件**；`.venv-mineru` 的 `pyvenv.cfg` 锚定旧机用户；`RESEARCHER_SCAN_ROOT` 指向不存在目录 → **扫描静默空转**；tools 层 **43 处**盘符字面量。
→ **路径走配置/环境变量；CI 断言无盘符字面量。**

**D2 产物根与备份根混乱**
`work/.archive/` 30 个子项记录六轮布局变更：`BackupPaper-*` 三个早期命名不统一；`BackupPaper-2026-W99-fake21B`（**伪数据混入备份面**）；`BackupPaper-opencode-residue`（无关文件污染）；`D-legacy-20260919`（迁移只复制不删除，D 侧留副本）；`D-datasets-legacy-20260920`（曾把 204 条 claims 发布为 CC-BY 数据集，**与"止于 Idea 交付"冲突**）；`D-papers-orphan-20260920`（**关于本 OS 的论文草稿**，scope 外）；备份 registry 的 `_note` 与磁盘实况不符。
→ **三类根在 canon 一次性定义；备份面只增不改；备份清单由程序生成。**

**D3 沙箱/工具链环境事实（须写入 V2 契约）**
`oc-research.ps1` 在 AI 会话内 **exit 0 但 stdout 为空**；会话注入 `HTTP_PROXY` → `localhost:23119` 假 502；stdlib 证书池无效 → 需代码内 certifi 兜底（**用户级 `SSL_CERT_FILE` 已删，勿写回**）；MinerU 冷启动 ~42s → 探针超时须 ≥120s（曾因 30s 误判不可用）；GUI 进程活不过单条 Bash 命令；跑全量 pytest 前需 `CODEBUDDY_SAFE_DELETE_ENABLED=0`。

### E. 方法论域（4 条）

**E1 用"堆功能"回应外部刺激 → 随后批量删除**
证据：09-02 `4410509`（8-item high-star）+ `53b68b4`（10 skills）→ 09-03 `079d82f`（32-repo borrow，`uv.lock` 从 302 KB 一次涨到 **1.21 MB**）→ 09-05 单日 **21 个提交**（全仓最高）→ 随后 2–19 天内批量删除（`52c254d`/`7c677ca`/`85dbd9d`/`f287d32`/`14ac969`）。
→ **无当次任务需求的能力，不引入。**

**E2 报告产出 > 消费能力**
`project-objective-review` 原文「报告产出速度超过消费速度，存在**"为优化而优化"倾向**」；`outputs/archive/reviews-202609/` 一次性归档约 28 份，README 自评"未随代码演进更新"。
→ **每份报告必须绑定一个已执行的改动。**

**E3 无分支隔离，直接在线改生产**
130 个 commit **全部在 `master`**，无 feature branch、无 stash。
→ **结构性改动走分支 + 验证后合并。**

**E4 归档而非删除**
反复"先归档、后删除"：`_legacy_archive/`（8 天后删）、`_deprecated_archive/`（11 天后删）、`cli_*.py`（2 天后删）。
→ **删除就是删除；需要保留证据时只留"文件名清单 + 删除理由"。**

---

## 4. 红线清单（第一天不变式 12 条 + 九组 52 条）

> 完整版见 `knowledge/legacy-detours.md`（含每条证据与核验表）。此处列规则本体。

### 4.1 第一天不变式（其余都是推论）

1. 一个 canon 文件，无镜像/无指针层
2. 每个策略值只有一个机器可读来源，且断言无副本
3. 每个状态文件只有一个写入者，且有对账通道
4. 冻结前归一字节，冻结后任何人只读不动
5. 所有输出根走环境变量，测试默认重定向
6. 只有证据充分性可以当硬门禁
7. 门禁自身必须有测试
8. 反馈覆盖率是第一屏数字，低覆盖时禁止扩大供给
9. 认知决策在会话内做，自动化只管机械步骤
10. 产物/缓存/备份不进版本库
11. git 先于一切；结构性改动走分支
12. 外部能力 borrow-not-merge，过端到端验收

### 4.2 九组红线

**A 单一真源**：A1 规则只活一处 · A2 锁内容哈希不是 mtime · A3 领域本体进数据、代码只当解释器 · A4 组织形式不反复震荡 · A5 同类配置只声明一处 · A6 禁止落盘快照

**B 状态与账本**：B1 每文件单写者 · B2 账本与 run.json 必须一致且要有一致性体检命令 · B3 字段建了就要流转 · B4 先写盘再冻结 · B5 失败账本如实记 · B6 不留悬挂 active run · B7 实物产出不得跑在记账前面

**C 门禁与治理自指**：C1 门禁不能自身有 bug · C2 达标不能自证 · C3 禁静默吞异常 · C4 门禁可豁免且留痕 · C5 配额/覆盖/日历类不得为硬门 · C6 质量机制总量封顶（每加一层废一层）· C7 外部闸门只能 soft · C8 canon 内不得自相矛盾

**D 范围与欠债**：D1 新能力过立项门禁 · D2 不因对标堆料 · D3 scope 钉死 · D4 borrow-not-merge · D5 build→prune 要有止损锚点 · D6 新功能须先在真实 run 上验证 · D7 不许建几天就推翻 · D8 never-landed 直接删

**E 环境与可重建**：E1 环境远离代码、一条命令重建 · E2 禁盘符/个人路径字面量 · E3 外部根名用唯一常量+回归门禁 · E4 写通道边界如实承认 · E5 SSL 走代码兜底 · E6 迁移先 dry-run · E7 冻结工件不可改

**F 反馈与验证回路**：F1 唯一验证信号必须真实闭合 · F2 反馈优先于新供给 · F3 reject 必记失败账本 · F4 认知判断必须落成不可变、可被 verifier 复核的 artifact · F5 深读由 idea 驱动 · F6 不承诺全量、只承诺按需

**G 工程细节**：G1 统一写入器（UTF-8/LF/尾换行/排序）· G2 哈希范式一次定死 · G3 改字节的钩子必须 exclude 冻结目录 · G4 测试隔离 + 污染守卫 · G5 一开始就小模块 · G6 孤儿随时清 · G7 CLI 不并行双套 · G8 交付物进持续门禁

**H 顺序与节奏**：H1 先收敛存量再铺新供给 · H2 不用新机制治旧机制的副作用 · H3 无分支隔离 = 在线改生产

**I 认知与自动化边界**：I1 认知决策永远在会话内 · I2 规则总量正比于真实决策数而非焦虑 · I3 每份报告绑定一个已执行改动

---

## 5. 数字核验声明

外部扫描清单的方向与结论基本可靠，以下经实测修正：

| 外部表述 | 实测 | 处理 |
|---|---|---|
| "7GB 仓库" | 仓库本体 ≈ **1.4 GB**；环境 **6 GB**（`.venv` 1.4 G + `.venv-mineru` **4.6 G**） | 数字成立，须拆分"仓库"与"环境" |
| "`literature_search_tools.py` 2367 行" | 峰值 **2396 行** | 修正 |
| "`oc_research_os.py` 曾 3000+ 行" | 峰值 **9576 行**（`034440c`） | **严重低估**，修正 |
| "marketplace v0.4.0" | 确证（10 skill，`install: hermes skills trust .`） | 采用 |
| "34 idea 只 7 条失败" | 确证（`idea_failure_ledger.json` entries = **7**） | 采用 |
| "一周内建一周内埋" | 实为 **2–19 天**（`cli_*.py` 极端案例 2 天） | 修正 |
| "deprecated 三天后" | 未找到佐证 | 不采用 |
| "6 个零消费 .py" | **2 个零消费 + 4 个半孤儿** | 修正 |
| "run.json 17 候选 / 19 深读而 report 空白" | **未能复现该组合** | 不采用（问题本身成立，见 B2） |
| "equilibrium 六维 4.5/5" | 确证 | 采用 |
| "TEST-* 109 周索引 + 135 历史条目" | 确证（`a378a17`） | 采用 |
| "RUN_RESEAL 6 个 run" | 确证（`RUN_RESEAL` 6 次 + `RUN_REFREEZE` 9 次） | 采用 |

**本次新实测到的账本断裂（V1 现存，硬证据）**：

| run | paper_candidates | candidate-ledger | 判定 |
|---|---|---|---|
| `WEEKLYRUN-20260814-094518` | 14 | **0** | 账本缺失 |
| `WEEKLYRUN-20260902-104920` | 15 | **0** | 账本缺失 |
| `WEEKLYRUN-20260818-134225`（等 5 个） | 0 | **1** | 孤儿 ledger 行 |
| `WEEKLYRUN-20260913-151819` | 16 | 16 | seeds=**0**，未收口 |

---

## 6. V2 现状诊断

### 6.1 已正确吸收（12 条）

| 教训 | V2 位置 |
|---|---|
| 单写者：run.json 唯一真源，ledger 是派生视图 | `pipelines/runs.py:100` |
| 预筛走侧账，经 reconcile 由同一写入者晋升 | `runs.py:125` / `runs.py:144` |
| LF 归一 + CRLF 变体容忍 | `common.py:64`；`runs.py:222` |
| 审计式重冻结（reason 必填 + history） | `runs.py:231` |
| 空 run 守卫（≥2 active 阻止新开） | `runs.py:48-54` |
| 减速期 seeds 硬门豁免 | `runs.py:195` |
| canon 单真源 + identity 断言 | `canon.py:27` |
| permissions 真执行 + 双向无孤儿审计 | `permissions.py:46` |
| 交付分层，core 即完整 | `idea.py:117,120` |
| 反馈回路 CLI（reason 必填 + reject 写失败账本） | `idea.py:63` |
| 可再生成物不进版本库 | `.gitignore` |
| 核心依赖最小化（3 个） | `pyproject.toml` |

### 6.2 已复发（10 条，含 3 处现存 bug）

| 红线 | V2 位置 | 现状 | 严重度 |
|---|---|---|---|
| A2/A3 | `runs.py:21`（`L2_MIN, L2_MAX = 10, 15`）、`idea.py:15`（`QUALITY_DIMS`）、`idea.py:26`（`need={3,1,1}`）、`papers.py:10`（`L3_PATHS`）、`idea.py:117`（`CORE_FILES`） | **策略数值双写 5 处**；canon 里全有同名定义，而 `canon.check_identity_sync()` **只校验 Zotero 两项** | 🔴 |
| C8 | `runs.py:20` vs `literature.py:14` | **路由枚举两套且不兼容**：`counter_boundary` vs `counter`/`boundary`；按后者填表会被 `add_paper` 直接拒 | 🔴 |
| G11 | 无 `.git` / `.github/` / `.pre-commit-config.yaml` | 无版本控制——V1 最有价值的资产就是 130 个 commit；且 G4 的守卫依赖 git | 🔴 |
| B6 | `runs/weekly/WEEKLYRUN-20260920-120000/` | 悬挂空 active run | 🟠 |
| G4 | `tests/conftest.py` **仅 4 行** | 无污染守卫；隔离靠手写 `monkeypatch` 打 8 个路径常量，漏一个即写穿真实仓库 | 🟠 |
| C5/C6/F6 | canon `week_modes`(2:2 自适应)、`parallel`(6/5/4/4/5)、`runs.finish_gates.l2_quota`(hard)、`deep_read.templates`(v3 模板) | **搬回 V1 已证伪的机制**——正是 V1 调参后 OOM、被去周化、被废除配额的那一组 | 🟠 |
| E1/E2 | `common.py:22-25` + canon `identity` | 绝对路径仍进仓（已集中，但 `check_identity_sync` 不校验路径） | 🟠 |
| C4/E4 | `permissions.py:37-38` | `allow_with_recent_backup` **假严格**：直接放行 + 注释"由 caller 校验"，但没有 caller | 🟠 |
| G6 | `runs.py:267-268`（`void = ...; _ = void`）、`validate.py:68-69`（空操作）、`pipelines/papers.py`（无 CLI 入口）、`delivery/`、`integrations/`（空目录）、双版本 `__pycache__` | 死代码与半成品痕迹 | 🟡 |
| G7/A5 | `pyproject.toml` 的 `vector` extra(chromadb)；`claims.record_verdict` 全量重写 vs `append_claim` 追加；`validate.REFERENCED_ACTIONS` 手工维护 | 休眠依赖 + 同文件两种写模式 + 元数据手工同步 | 🟡 |

### 6.3 尚未覆盖（6 条）

版本控制 + CI + pre-commit（G11）· 仓库污染守卫（G4）· 备份机制与前置校验（对应 `permissions.json` 里那条无实现的策略）· 存量反馈消化机制（F1/F2）· 交付卫生检查（V1 DEC-0032 三条规则）· 文档腐烂防护（I3）

---

## 7. 整改路线

### P0 —— 写任何业务代码之前

1. `git init` + `.gitattributes`（`* text=auto eol=lf`）+ 首次提交
2. 删 `runs/weekly/WEEKLYRUN-20260920-120000`；加"active 且 papers=0 超 24h 即报错"的校验
3. 修 **5 处数值双写**（全部改为 `canon.get(...)`），并新增 `test_no_duplicated_policy_literals`
4. 修 **路由枚举矛盾**：canon 新增 `coverage.routes`，两处都从它读，删除 `DISCOVERY_CLASSES`
5. 删死代码与空目录（`runs.py:267-268`、`validate.py:68-69`、`delivery/`、`integrations/`、`__pycache__`）；`papers.py` 接线或删除
6. 测试隔离改造：全部输出根环境变量化 + `conftest.py` 加 session 重定向与 `git status` 污染守卫
7. 修"假严格"：`allow_with_recent_backup` 要么真校验备份新鲜度，要么降级为 `allow` 并删误导语义

### P1 —— 骨架定型

8. 按"V1 用它成功过吗"逐条过滤 canon：`parallel` 数值、`week_modes`、L2 配额硬门、v3 模板
9. `check_identity_sync()` 从"只查 Zotero 两项"扩展为遍历全部常量（含路径）
10. 补 CI + pre-commit（`pytest` / `ruff` / 盘符扫描 / 文档数值扫描；pre-commit 必须 `exclude: ^runs/`）
11. 补交付卫生（slug 合法性、absorbed 判定、测试禁用真实交付根）
12. 补文档腐烂防护（README 命令必须存在于 parser）
13. `session-brief` 输出"规则触发率"，触发率为 0 的规则进退役候选
14. 固化 `docs/ENVIRONMENT.md`（D3 那 6 条沙箱事实）

### P2 —— 业务铺开前

15. 明确存量反馈来源（V1 的 29 个 `researcher-decision.json`）与回填流程
16. `knowledge/` 占位数据落位或删除（`gap-map.md`/`living-queries.json`/`feasibility_profile.json` 现有"种子待收口"类占位）
17. canon 每条规则带 `test_ref`，`validate` 能报"无测试覆盖的规则"
18. 建立"十角度自查"方法（V1 的 `project-deep-review` 模式），作为每个里程碑的固定动作

---

## 8. 收官

> **别让系统越来越擅长"看起来正确"，而要让产出的证据能被外部核查。**

V1 约 95% 的弯路都收束在这一句里：无人值守执念、堆料对标、门禁自证、多份真源、反馈空转、无限重写——**全是它在追求"治理上无懈可击"，而不是"研究产出可验证"。**

V2 唯一的护身符，是第一关先跑出一个**带 verdict + 真实研究者反馈**的 idea。跑出来，就赢过了 V1 整个治理层。

---

## 附录 A：文档地图

| 文档 | 定位 |
|---|---|
| **`docs/FINAL-REPORT.md`**（本文） | **单一入口的最终报告**：摘要 + 基线 + 24 条弯路 + 52 条红线 + 核验 + V2 诊断 + 路线 |
| `docs/V1-RETROSPECTIVE.md` | 证据档案：24 条弯路的逐条完整证据链（commit 时间线表、原文摘录） |
| `knowledge/legacy-detours.md` | 纪律清单：12 条不变式 + 九组 52 条红线（每条带伤疤证据）+ 核验声明 |
| `docs/V2-ACTION-ITEMS.md` | 可勾选整改清单（含验收标准） |
| `governance/workflow_authority.json` | V2 的 canon（单真源） |
| `knowledge/anti-pattern-cards.md` | V2 的反模式卡（AP-01~05；V1 最终为 AP-01~08） |

## 附录 B：证据索引

**关键 commit（V1）**

| 主题 | commits |
|---|---|
| 哈希/parity 死循环 | `0340b1a` `2468504` `d72cbd2` `5d8ac8f` `b967b83` `153d4a8` `e2d7cb4` `473f381` `318f162` `efa8faf` `42b3a17` `79825bc` `bd88f83` `e5843d7` |
| parity 机制退役 | `34fc4ba` |
| 测试污染 | `07dadab` `758ba1d` `6feb4b5` `a378a17` `fb5e56e` `734e5d5` `284f1ed` |
| 规则 shim 化 | `9cf92e7` `f36d814` `051e1a4` `a64484f` `3ccf864` `79825bc` `59456d4` |
| 90min 残留 | `3e55930` `a64484f` `2938d6f` |
| 神文件拆分 | `a64484f` `d736df9` `e6d8fa0` `52c254d` `d01a138` |
| 外部堆料与清理 | `4410509` `53b68b4` `079d82f` `20c66c4` `52c254d` `7c677ca` `85dbd9d` `f287d32` `14ac969` |
| Zotero | `52f0f61` `c44bf67` `72b4505` `fc6d288` |
| 路径/迁移 | `2903b23` `92a2542` `8611d8e` `4f99e31` |
| 去周化/节律 | `df62667` `8692b05` `c7d1d07` `34fc4ba` `58f16d1` `c0581ad` |
| 检索通道 | `387053c` `eccc82c` `1556d12` `0d1fb06` |

**关键文件（V1）**：`outputs/project-audit-2026-09-05.md` · `project-objective-review-20260905.md` / `-r2.md` · `project-deep-review-20260914.md` · `project-path-ownership-and-parity-review-20260920.md` · `legacy-cleanup-2026-09-05.md` · `skill-integration-map-20260905.md` · `github-benchmark-2026-09-13.md` · `idea-verification-report-20260905.md` · `idea-pool-triage-proposal-20260905.md` · `project-environment-adaptation-{checklist,executed}-20260919.md` · `oc-research-os/governance/{workflow_authority.json,decisions.json,permissions.json}` · `AGENTS.md` · `tools/core/{runs.py,common.py,validate.py}` · `.workbuddy/memory/MEMORY.md`

**V2 被点名位置**：`pipelines/runs.py:20,21,267-268` · `pipelines/idea.py:15,26,117` · `pipelines/papers.py:10` · `pipelines/literature.py:14` · `pipelines/validate.py:68-69` · `pipelines/permissions.py:37-38` · `pipelines/common.py:22-25` · `tests/conftest.py` · `runs/weekly/WEEKLYRUN-20260920-120000/` · `governance/workflow_authority.json`

---

*本报告所有量化结论均有命令输出或文件内容佐证。唯一未证实项：`BackupPaper-2026-W99-fake21B` 的命名含义。V2 状态快照时间：2026-09-20 23:11。*
