# V1 弯路复盘与新仓设计依据

> 审计对象：`D:\AppData\Opencode\Project\科研-Idea`（下称 **v1**）
> 目标仓：`D:\AppData\Project\Idea`（下称 **v2**）
> 审计时间：2026-09-20
> 证据范围：130 个 commit 全量 message、37 条 DEC、1145 行 canon、`outputs/` 全部自审报告、`work/.archive/` 全部归档项、v1 现行代码与测试、v2 全部代码（1615 行）
> 标注约定：**（已验证）**= 有命令输出/文件内容/commit 佐证；**（未证实）**= 仅有间接线索。

---

## 0. 结论先行

v1 不是"写坏了"，而是**六周内把治理、工程、业务三条线各自都做成了自我维护的负担**。它自己给出的诊断最准确：

- `outputs/project-audit-2026-09-05.md`：「总评：6.3 / 10 —— 设计成熟（A-），执行落差（C+）」
- `outputs/project-objective-review-20260905.md`：「这个系统当前最大的敌人不是外部检索质量，而是自身的复杂度维护成本。」
- `outputs/project-objective-review-20260905-r2.md`：「下一阶段的主要矛盾已从"建成管道"变为"给系统减重"。」
- `outputs/project-deep-review-20260914.md`：「当前最大风险不在代码，而在运行时状态熵与反馈回路未启用。」

因此 v2 的第一原则不是"把 v1 的功能重写一遍"，而是：

> **凡是 v1 用"再加一层机制"解决的问题，v2 一律改用"删掉问题的来源"。**

v2 骨架（16:17–16:25 建立）已经正确吸收了 v1 约 12 条最重要教训，但审计发现在**第 1 天就已经有 10 处旧病复发**，其中 2 处是现存 bug 而非隐患。这些必须在写第一行业务代码之前修掉，否则 v2 会以更快速度重演 v1（v1 从基线到第一次"清创决策"只用了 7 天）。

---

## 1. 事实基线（v1）

| 维度 | 实测值 | 证据 |
|---|---|---|
| 提交数 / 时间跨度 | 130 commits / 2026-08-11 → 2026-09-20（41 天） | `git rev-list --count HEAD` |
| 分支 | 仅 `master`，无任何 feature branch、无 stash | `git branch -a` |
| 仓库体积 | `.git` 420 MB；`oc-research-os/` 549 MB；`work/` 464 MB | `du -sh` |
| 曾入库的可再生成图 | 2774 张 PNG ≈ 当时 tracked 文件的 70%（4584 中） | `.gitignore:67-70` 自述 + `git ls-tree` |
| canon | 1145 行 / 75 KB，被改 33 次 | `git log -- workflow_authority.json` |
| AGENTS.md | 被改 26 次，曾 325 行 → 瘦身到 44 行 → 又长回 15 KB | `9cf92e7`、`59456d4` |
| 决策 | 37 条 DEC（DEC-0001~0037） | `governance/decisions.json` |
| 工具链 | 75 个 CLI 子命令；`tools/` 23959 行；191 个测试 | `pytest --collect-only` |
| 依赖 | 核心 6 个，`uv.lock` 1.03 MB / 172 packages（曾 8 KB → 1.21 MB） | `git cat-file -s` 采样 |

**失效指标（即"捷径没走通"的量化结果）**：

| 指标 | 结果 | 来源 |
|---|---|---|
| 声明的核心环节 L3 深读达成 | 3/12 run；真正 `verified_l3` 仅 10 篇（`reading_state.json` 90 条） | `project-audit-2026-09-05.md` |
| 13 件交付完整度 | 2/34（后按 core-4 重定义） | 同上 |
| Zotero 人工决策环流转 | `zotero_membership_plan` / `decisions_requested` 全程 0 条 | 同上 |
| 唯一验证信号（研究者反馈） | 15 天后仍 0 条记录，29/29 verdict 缺失 | `project-deep-review-20260914.md` |
| 检索通道净产出 | 引入过约 14 个通道 → 现役 3 个（OpenAlex/Crossref/arXiv） | `mechanized_retrieval.py` |
| 供给 vs 消化 | 40 个 idea slug vs 每周 1–2 个 champion 名额 | `project-objective-review` |
| 每周 run 收口 | 13 个 weekly run 中 5 completed / 8 partial | `runs/weekly/*/run.json` |
| 静默吞异常 | 约 95 处 `except Exception: pass` | `project-audit-2026-09-05.md` |

---

## 2. 弯路全录（24 条，按域归类）

### A. 治理域（5 条）

---

#### A1. 规则多副本 → "真 shim 化"反复 5 轮

**现象**：同一批规则文本同时存在于 `AGENTS.md`、`coordination/*_prompt.md`、`literature/*_contract.json`、`governance/workflow_authority.json` 四类文件中。每次改一处就产生漂移，于是反复"上收 canon + 把下游改成指针（shim）"。

**证据（已验证，按时间序）**：

| 日期 | commit | 方向 |
|---|---|---|
| 08-22 | `9cf92e7` | `prompts 4→2 shim（weekly 20→1.6KB + idea 11→1.2KB pointer）` |
| 08-23 | `f36d814` | `weekly_cycle 规则上收 canon(contract 真 shim 化<1KB)` |
| 08-23 | `051e1a4` | 标题原文：**`DEC-0010 anti-oscillation endgame - contracts become true shims`** |
| 08-23 | `a64484f` | `AGENTS指针化(移除qwen矛盾/90min残留)` |
| 08-30 | `3ccf864` | `canon 1052->980 ... canonical slimming` |
| 09-05 | `79825bc` | `canon dual-source removal` |
| 09-05 | `59456d4` | `AGENTS.md de-numbered 4 canon restatements into pointers` |

作者用词 `anti-oscillation endgame`（反振荡终局）本身就承认了此前在"真做/假做 shim"之间来回摆动。

**根因**：把"单一真源"当成一个要靠**机制**维护的属性（shim 体积断言、悬空锚点断言、STALE 域豁免），而不是靠**物理上只有一个文件**。

**代价**：7 个 commit、跨 14 天的治理工时；直到 09-05 仍在删 `governance/canon/*.json` 死副本（DEC-0031）。

**→ v2 规则**：只允许一个 canon 文件。禁止 shim / 镜像 / 指针层 / "数值型契约"。文档复述数值即为缺陷。

---

#### A2. 策略值散落硬编码（同一数值多处副本）

**现象**：同一个策略值在 canon、代码、文档里各写一遍，改一个忘一个。

**证据（已验证）**：

- **90min 硬上限**被删 3 次：`3e55930`（canon 废止）→ `a64484f`（AGENTS 移除残留）→ `2938d6f`（`automation-run-start 硬编码 90min cap 残留清除`）。三次跨同一日。
- **Zotero 集合根名** 13 处硬编码。`72b4505` 原文：「`13 hardcoded old-name sites would have silently misrouted imports — worst case zotero_cmds.py:737 *created* a fresh empty "opencode" root when the lookup missed.`」→ 最坏情形是**静默新建空集合、数据进错地方且无报错**。
- `oc_research_os.py` 曾有"8500 行上限"规则，但文件实际涨到 9576 行（超限 1000+），规则先失效后追认（`d736df9` 自述 `monolith cap 8500->6900`）。

**根因**：没有"副本检测"这个动作。规则只在人脑里，不在 CI 里。

**→ v2 规则**：每个策略值只有一个**机器可读**来源，且用测试断言"不存在第二份副本"。见 §3.2 的复发清单——v2 目前**已经有两份了**。

---

#### A3. canon 双源 + 快照腐烂

**现象**：把 canon 拆成主文件 + `governance/canon/*.json` 分片（DEC-0028），立刻产生漂移，5 天后（DEC-0031）又删掉。

**证据（已验证）**：
- DEC-0028（08-31）：「canon 拆 `canon/*.json`」。
- DEC-0031（09-05）：「`governance/canon/*.json`（DEC-0028 拆分产物）零消费方且与主文件漂移」→ 删除。
- `project-objective-review-20260905.md` 原文：「canon 双份存储且已漂移 … **违反项目自己的 single-source-of-truth 原则，且已腐烂**」。
- 同类：`project-objective-review-20260905-r2.md`「**快照腐烂** … 上下文注入层在消耗过期信息」——`zotero_exports` 快照 171 项 vs 实况 11 项；`outputs` 快照 71 vs 实况 7；`AGENTS.md` 残留数值「违反其自己声明的"不复述数值"原则」。

**根因**：任何"在某时刻复制过来"的快照都会腐烂。项目自己在 `AGENTS.md:33` 写下了这条，又自己违反。

**→ v2 规则**：上下文注入层只允许**实时生成**（每次 session-brief 现算），禁止落盘快照作为后续依据；确需缓存的必须有 TTL + 生成时间戳 + 校验。

---

#### A4. 门禁多而软、反复软化

**现象**：canon 声明 14 个 gate 键（`corpus_gate`/`coverage_gate_ref`/`evidence_completeness_gate`/`hard_gates_per_candidate`/`journal_quality_gate`/`l4_lite_gate`/`literature_search_gates`/`relevance_gate`/`seeds_gate_supply_hold` 等），18 处 `hard`、17 处 `warn`、8 处 `soft`。之后几乎每隔几天软化一个。

**证据（已验证，hard ↔ soft 摆动 5 次）**：

| 日期 | commit | 动作 |
|---|---|---|
| 08-22 | `9cf92e7` | `soften banner coverage/L3 hard→warn` |
| 08-23 | `3e55930` | 收紧：`检索硬闸(Q2/relevance0.65分通道/second_pass硬失败)` |
| 08-23 | `051e1a4` | `weekly-close warn vs per-paper hard split` |
| 08-29 | `8692b05` | 再收紧：`weekly L3 all 10-15 hard` |
| 08-31 | `776f37f` | 放松：`journal_Q2 hard removed, soft_reference_only` |
| 09-05 | DEC-0035 | L3 固定配额整体废除，改 idea 驱动 |
| 09-13 | DEC-0037 | seeds 硬门在减速期加豁免 |

**且 canon 内部自相矛盾（已验证，2026-09-20 仍存在）**：同一 L3 门禁在主文件里同时有三种说法——`:992`「L3 不按固定配额考核」、`:263`「weekly L3 requires all 10-15 candidates L3 (hard)」、`:1095`「all 10-15 candidates, hard per」、`:700`「已 2026-08-29 置 none」。

**根因**：门禁被当成"表达焦虑"的工具，而不是"表达约束"的工具。**凡是被反复软化的门禁，说明它本来就设错了。**

**→ v2 规则**：只保留"证据充分性"类硬门禁（有无标识符、有无二次验证、有无撤稿信号、交付文件是否齐备）。**配额类、覆盖率类、日历类一律不得设为硬门禁。**

---

#### A5. 声明超前于实现

**现象**：canon / 文档里声明的机制、通道、能力，代码里并不存在或从未跑通。

**证据（已验证）**：

- `zotero_proxy_guide.md §6` 曾宣称"5-channel fanout + 第 6 个 Lens 通道"——实际只有 3 个源，Lens 从未实现（`0d1fb06` 专门纠错）。
- `1556d12` 称 pubmed_search / Lens「never implemented and never declared in canon」——但 `git show 74950f6:tools/literature_intake.py:370` 确实有 `def pubmed_search`，措辞与历史不符。
- `.env` 里的 `LENS_API_KEY` / `NCBI_API_KEY` 全仓无消费方（实测 Lens 401、NCBI 200），文件存活 20 天后随归档删除。
- canon 的 `facts_card.automation` 被迫写：「事实卡与 gap-map 的全量渲染**待 claims 库覆盖度提升后启用**…在此之前两者仍人工维护——**声明不超前于实现**」。这句话本身就是病症的证明。

**→ v2 规则**：文档只写"代码实测存在的能力"。新增一条 canon 规则时，必须同时落一个能失败的测试。**做不到测试的规则，不写进 canon。**

---

### B. 工程域（7 条）

---

#### B1. 冻结哈希 × 改字节钩子对撞（最严重，30 天）

**现象**：同时引入"文件内容哈希冻结"（防事后篡改）和"pre-commit 强制改字节"（`end-of-file-fixer`/`trailing-whitespace`/`ruff-format`），两者形成机制级死锁：冻结 → 提交 → 钩子改字节 → 哈希失效 → 人工重冻结 → 再提交 → 钩子又改……

**证据（已验证）**：

- `parity_manifest.json` 被 **33 次 commit 触达**（全仓第 2 高）。
- `e2d7cb4` 标题自称"根治"，正文原文：「`parity 死循环根治……Root fix for the historical freeze→commit→hook-normalize→re-freeze loop (commits 153d4a8..a64484f era, 11 manifest rewrites)`」。
- **"根治"后仍继续重冻结**：`473f381`、`318f162`（同日晚）、`034440c`、`efa8faf`（再立 DEC-0011 `RUN_RESEAL precedent`）、`42b3a17`、`79825bc`、`bd88f83`、`e5843d7`（`refreeze #6`）。
- 单 run 极值：`WEEKLYRUN-20260904-092350/run.json` 的 `refreeze_count = 6`。
- `state.json` history 实测 `RUN_REFREEZE` 9 次 + `RUN_RESEAL` 6 次。
- 最终结局：**整包删除机制**（`34fc4ba` `remove parity/refreeze machinery: manifest, refreeze tool, validate_parity_drift, pre-commit parity hook`）。
- 残留成本：只能给 `.pre-commit-config.yaml:15-20` 加 `exclude: ^oc-research-os/runs/` 整片豁免；只能让哈希函数接受 CRLF/LF/有无尾换行多种字节变体（`common.py:sha256_file_variants`）——**这在语义上削弱了篡改证据本身**。

**代价**：约 18 次重冻结提交，跨 30 天（08-15 → 09-14）。

**→ v2 规则**：字节归一化只能发生在**冻结之前**，且是**唯一入口**（`common.write_json` 已做到 LF + 尾换行）。冻结后不得有任何进程改写该文件。若一定要用改字节的格式化钩子，钩子必须 `exclude` 冻结目录。

---

#### B2. 同一"防漂移"机制重复造三遍

**现象**：`frozen_hashes`（run 层）、`parity_manifest`（contract 层）、`skills-lock`（skill 层）是同一个需求的三种实现，各自踩同一个坑。

**证据（已验证）**：
- `skills-lock.json:5` 自述：「`v1 (2026-08-22) 只记 mtime + version:'unknown'，无法检测 skill 内容漂移；v2 pin 每个 SKILL.md 的 SHA256`」——v1 的坑（不记内容哈希）与前两者**完全同型**。

**→ v2 规则**：一个内容哈希原语（`common.sha256_text`）＋一处实现，所有需要"防漂移"的地方复用它。

---

#### B3. 测试污染真实仓库（跨 26 天、8 次）

**现象**：测试直接写真实工程目录，fixture 被提交入仓。

**证据（已验证）**：

| commit | 清除规模 |
|---|---|
| `758ba1d` | 从追踪移除 145 个 pytest IDEARUN + 164 个 RECOG + 135 个 zotero scan fixture = **2395 文件** |
| `6feb4b5` | `purge pytest handoffs/IDEARUN pollution, compact state history` |
| `a378a17` | `state.json` 清 109 条 weekly index + 135 条 history pytest-leak（单文件 −1035 行） |
| `fb5e56e` | `isolate eval-report writes in publish-gate tests`（曾写穿真实 `oc-research-os/reports/eval-2026-09-05.json`） |
| `734e5d5` | `fix(idea): scope delivery-root defaults (CI leak)` |
| 09-13 | `idea-delivery-test-residue`：**测试残壳落进真实交付根** `E:/Idea/`（`C1`/`conformal`/`sensor-informed`/`title-c1`） |

`tests/conftest.py` 自述的两条成因：「生产命令**直接写** `oc-research-os/`，测试未隔离」；「`IDEA_DELIVERY_ROOT` 默认绝对路径 `E:/Idea`，在 Linux CI 上变**相对路径**，跑出仓库内的 `D:/...` 树」。

**v1 最终产出的有效方案（v2 应直接搬）**：
1. session-scoped autouse fixture：会话首尾快照 `git status --porcelain`，diff 非空即 fail。
2. 所有写路径常量环境变量化（`OC_STATE_PATH`/`OC_WEEKLY_RUN_ROOT`/`OC_IDEA_DELIVERY_ROOT` …）。
3. legacy 路径设哨兵，禁止复活。

**→ v2 规则**：见 §3.3——**v2 目前没有这道防线**。

---

#### B4. 可再生成物入库

**现象**：文献识别流程把论文页裁切成 crop PNG 用于公式核验，这些图被提交进 git。

**证据（已验证）**：
- `.gitignore:67-70` 自述原文：「`2774 pngs were ~70% of tracked files and the main .git bloat driver`」。
- 清理 commit `eea05ea` 原文：「`2774 regenerable PNG crops removed from index only; local files kept. History rewrite deferred (DEC-0019 stands).`」→ **只 untrack 不重写历史，`.git` 里永久残留 2285 个 png blob / 68 MB**。
- 单文件级：`RECOG-20260831-112239/run.json` 1.52 MB；`oc-research-os/runs` 下 1132 个 tracked 文件（822 个 json）；历史对象中 json 2996 / png 2285 / md 1438，而 py 仅 503。
- 备份 zip 被放在仓库内：`oc-research-os/backups/opencode-clone-clone-20260913-131327-*.zip` = 209 MB。

**→ v2 规则**：`runs/`、crops、PDF、缓存、备份一律不进版本库。**v2 的 `.gitignore` 已经做对了**（`work/`、`*.pdf`、`**/crops/`、`*.png`、`*.zip`），保持。

---

#### B5. 无真锁的状态写

**现象**：所有状态文件是"读全量 → 改 → 全量写回"，无锁、无 CAS。

**证据（已验证）**：
- `common.py:load_state/save_state` 无锁，`revision` 仅自增；并发写互相覆盖。
- `acquire_lock/release_lock` 是**基于 mtime 的 600s 陈旧锁**（不是互斥），且全仓**只有 backup 一处调用**，状态机路径完全没锁。
- `state.json` revision 曾 2721 → 572（测试污染 + 一次人工清理的结果）。

**→ v2 规则**：单机单进程场景下，**不引入锁机制**（v1 证明它是装饰品）；改为"每个文件只有一个写入者"的**结构性保证**（v2 的 single-writer 已做对）；跨进程写同一文件是设计缺陷，不是加锁能解决的。

---

#### B6. 自建宿主已提供的能力（skill 编排子系统）

**现象**：在宿主（OpenCode/WorkBuddy）已有 skill 机制的前提下，又自建了一套 skill 注册 + 编排子系统。

**证据（已验证）**：
- 自建物：`tools/skill_registry.py`(118 行) + `tools/agent_orchestrator.py`(257 行) + `tools/skills/`（11 个包，各含 `SKILL.md` + `skill.yaml`）+ `tools/tool_manifest.yaml`(52 行) + `tools/marketplace.json`(19 行)。
- 2026-09-13（`github-benchmark-2026-09-13.md`）仍在扩张："skill_registry 11 映射 + 新建 `tools/skills/idea-collision/`，registry validate passed=true"。
- **2026-09-14 `85dbd9d` 整批删除**：`remove internal skill orchestration subsystem (batch C2)`，30 files, +5/−683，理由："canon/CLI 零引用"。
- 最后一个 skill 包（idea-collision）仅存活 **1 天**。

**根因**：没有先问"宿主是否已经提供"。

**→ v2 规则**：引入任何子系统前，先写一句"宿主/现有依赖里为什么不能做这件事"。答不上来就不建。

---

#### B7. 死件与"从未落地"的能力

**现象**：大量"建了但没接线"或"声明了但从未安装"的模块，且会重复出现。

**证据（已验证）**：

| 对象 | 状态 | 证据 |
|---|---|---|
| `docling` | 18 天后删除；**历史验收是 `--help OK + dummy PDF extracted 0 tables / 0 formulas`，表格/公式通道从未工作** | `14ac969` |
| `qdrant-client` | 从未安装；每次 `VectorStore` 初始化打一条 ModuleNotFoundError WARN 后回落 chroma | `14ac969` |
| `tools/arxiv_html_meta.py`（4188 B）、`tools/claims_append.py`（4624 B） | **DOA**：除 `decisions.json` 提及外，CLI/core/tests 全无调用 | 全仓 grep |
| `tools/idea_collision.py`(21 KB)、`idea_rubric_loop.py`(12 KB)、`skill_distill.py`(13 KB) | 半孤儿：有测试和文档，但 core/CLI 不引用 | grep |
| `tools/_deprecated_archive/` | 把死代码"归档"而非删除，一周后整包删除 | `f287d32` |
| `cli_*.py` 5 个文件 | 拆出来 2 天后推翻删除（`registry/admin/idea/literature/zotero/common, only referenced by their own guard tests`） | `52c254d` |
| `tools/_legacy_archive/` | 含 `research_os.py` **7413 行**、`literature_intake.py` 2276 行，归档 8 天后删 | `0bf00c5` |

**关键教训（`14ac969` 原文）**：「`docling was never installed (ModuleNotFoundError), and its historical acceptance was literally "--help OK + dummy PDF extracted 0 tables / 0 formulas". The table-formula channel never worked.`」

**→ v2 规则**：**outdated AND never landed → 直接删，不归档**。引入外部能力的验收标准是"端到端产出正确结果"，不接受 `--help OK`。

---

### C. 业务域（5 条）

---

#### C1. 承诺"全量 L3"→ 深度稀释 → 反复降级

**现象**：先定"每周 10-15 篇全部 L3 深读（hard）"，发现做不到，一路降级。

**证据（已验证）**：
- `8692b05`（08-29）：`weekly_deep_read_l3_requirement: 0/none -> 10-15 all hard`。
- `df62667`（同日，更早）：`cancel weekly L3 quota`。
- DEC-0023（08-30）：被迫改为「10-15 全量 L2 卡 + 3-5 篇 gap 命中升 L3」。
- DEC-0035（09-05）：**固定配额整体废除**，「纯检索 run 可 0 篇 L3 收口」。
- 结果：`reading_state.json` 90 条中 `verified_l3` 仅 **10 篇**；评审口径「L3 深读仅 3/12 个 run 达成 —— 最大短板」。

**同类过度工程（深读质量层 6 轮叠加，从未下线一层）**：

| 轮次 | 决策 | 加入的东西 | 实测使用率 |
|---|---|---|---|
| 1 | DEC-0003/0006 | agent_read 门禁 + 深读队列 | 队列后被废 |
| 2 | DEC-0018 | depth-v2 六小节 + anchor/lean 双档 + 事实卡 + 矛盾矩阵 | `Consistency-Check` 仅 47/151 篇 |
| 3 | DEC-0019 | writer-verifier 分离 + `deepread_lint` + `cold_recall` + 预习提问/两遍读法/Assumption Ledger/图理解五项 | **`cold_recall.py` 零产物（从未运行）** |
| 4 | DEC-0023 | claims 中枢 + 反模式卡 + gap 证据栈 + L2/L3 分层双路径 | — |
| 5 | DEC-0028/0029 | 全量 render 链 + 双模型 verifier + image 5 项 + 5 角色红队 + 8 攻击 + v3.1（SOTA 6 列 + 11 列 citation-support-bank） | 90 份 verify verdict 文件 |
| 6 | DEC-0035 | **唯一一次做减法**：废除配额 | — |

结果：depth-v2 / v3 / v3.1 **三代协议并存**；claims / facts / matrix / gap-map **四套知识视图**；writer / verifier / lint / cold_recall **四件工具**；实际 L3 论文 10 篇。

**→ v2 规则**：**先用最小深读把 90 篇跑满，再谈加层**。v2 的 canon 已经写了 `pre_reading_questions: 6` / `two_pass` / `figure_protocol_items: 5` 等一整代 v3 模板——这是把 v1 第 3 轮的东西原样搬进了 v2 第一天。见 §3.2-R6。

---

#### C2. 供给过剩 → 被迫装减速阀

**证据（已验证）**：
- `project-objective-review-20260905.md`：「当前 **40 个 idea slug vs 每周仅 1-2 个 champion 名额，孵化严重供过于求**，Idea 孵化速度与下游消化能力失衡」。
- `condensed-review-20260831.md`：「27 已交付中，**可作为毕业路径的仅 3 簇 4 个**」。
- 最终 DEC-0033 被迫增加 `portfolio.supply_policy`：pipelines 轨降频，「仅在研究者明确请求或出现新 gap 证据时触发」。
- DEC-0037 又打了补丁：减速期 `idea_seeds<3` 硬门需 `--supply-hold-reason` 豁免，否则无法收口。

**根因**：**先建生成器，后建消化器**。

**→ v2 规则**：**没有消化管道的生成器只会生产债务**。供给侧在反馈覆盖率 > 50% 之前不得提量。

---

#### C3. 反馈回路"建了不用"

**现象**：DEC-0035 把"研究者反馈"定为**唯一验证信号**，命令行也建好了，但从未被使用。

**证据（已验证，2026-09-20 实测）**：
- `oc-research-os/literature/idea-feedback.jsonl` **不存在**。
- 29 份 `E:/Idea/*/researcher-decision.json` 中 `researcher_verdict` **29/29 全部缺失**。
- `runs/idea-incubation/*/candidate-pool.json` 含 verdict 的文件数 = **0**。
- `state.history` 中 **0 条 IDEA_FEEDBACK 动作**。
- `outputs/idea-feedback-queue.md` verdict 列全为 `?`。
- `project-deep-review-20260914.md`：「28/29 交付仍是 agent-auto」。

**根因**：把"回路存在"当成"回路在工作"。

**→ v2 规则**：（a）存量 verdict 回填优先于新供给（v2 AGENTS.md 第 5 条已写对）；（b）**反馈覆盖率必须是 session-brief 的首屏数字**，让它无法被忽略。

---

#### C4. 检索通道铺开 14 个 → 现役 3 个

**证据（已验证）**：

| 通道 | 结局 | 原因 |
|---|---|---|
| OpenAlex | 存活（主源） | canon 限用纪律：高峰匿名限流 retryAfter 14–30s，只作 filter/ID 直取，不作主检索 |
| Crossref | 存活（补源） | 仅当 OpenAlex <8 或质量不足时补 |
| arXiv 直连 | 存活（`387053c` 新增） | 修的是**误诊**：所谓"arXiv 索引腐败（index ends 2026-07）"实为 MCP 瞬时故障 |
| Europe PMC | 保留 | public-apis 试点三项保留之一 |
| semantic-scholar MCP | 退役 | 三个 MCP（arxiv/semantic-scholar/pdf-mcp）指向旧机路径被删，2026-09-19 决定"不恢复" |
| paperscraper | 降级 | 拉入 botocore 1.43 与 s3fs 的 aiobotocore 冲突，被迫降级 botocore/boto3 |
| Lens | 幽灵通道 | **key 实测 401，通道从未实现** |
| pubmed_search | 先实现后删 | NCBI key 实测 200 但无消费方 |
| OpenReview | 离线 | 100% DNS 失败（SSL EOF） |
| Tavily | 休眠 | 无 key 即 skipped |
| zju-literature-downloader + `zju_fetch.py`（576 行） | 18 天后退役 | 依赖研究者本机 Chrome 登录 + CDP proxy + WebVPN，**长期不可用的不可自动化通道** |
| Ai2 Asta MCP | 未证实 | 仅文档提及，无实现痕迹 |

**→ v2 规则**：通道只保留能**自动、无人值守、端到端产出**的。依赖"研究者本机浏览器会话/人工 UI"的通道一律不引入（v1 的 zju 通道活了 18 天，两次 DEC 冲突后仍是人工约束取胜）。

---

#### C5. Zotero 链路被迫绕（外部约束 + 自加放大）

**约束来源判定（已验证）**：

| 约束 | 来源 | 说明 |
|---|---|---|
| Local API 只读（PATCH 501），写必须走 UI | **外部强加** | 初始基线 `research-os/02_zotero_workflow.md` 已写明，官方 API 只接受 GET |
| 不直接改 SQLite | **自加（安全取舍）** | 技术上可行，项目主动不碰 DB |
| 冻结幂等 JS + sha256 manifest + live readback + 7 天备份前置 | **自加（审计纪律）** | `oc-research-os/README.md:22` |
| import_queue 双位置 | **自己造成的 bug** | `zotero_ui_import.py` 同时定义 `IMPORT_QUEUE` 与 `IMPORT_QUEUE_CANONICAL`，两处实测均 0 文件 |
| membership-sync JS 缺 `.id` | **自加代码 bug** | `52f0f61`：生成 JS 有缺陷，必须人工在 UI 执行 |
| 集合根名 13 处硬编码 | **自加** | `72b4505` |
| master 集合从"必写"到"删除" | **研究者决策 + 历史包袱** | `fc6d288`：`总论文`/`codex`/`trae` 全部退出本地库 |

**净判定**：绕的根因是"API 只读"（不可规避），但**复杂度的主要放大器是自己加的审计层 + 硬编码**。

**→ v2 规则**：接受"Zotero 是半自动通道"这一事实，把它设计成**三段式显式流程**（生成 manifest → 研究者窗口执行 → 回读校验），不要把审计层做成额外人工卡点。v2 的 `zotero.py` 已朝这个方向（manifest + queue + readback 留白），是对的。

---

### D. 环境与路径域（3 条）

---

#### D1. 绝对路径硬编码（跨 36 天，迁移时总爆发）

**证据（已验证）**：
- `2903b23`（08-15）`fix absolute path refs`（第一次）。
- `92a2542`（09-19）：「`the repo was cloned from another machine whose roots (D:/APP Data\open code\..., C:/Users/users) no longer exist`」。
- 迁移清单（`project-environment-adaptation-checklist-20260919.md`）逐条定位：**代码层 10+ 文件、配置/治理层 14+ 文件**；`.venv-mineru` 的 `pyvenv.cfg` 锚定旧机用户路径；`RESEARCHER_SCAN_ROOT = E:\论文` 全机不存在 → **扫描静默空转**。
- tools 层共 **43 处盘符字面量**；`disproof_builder.py:102`、`figure_pipeline.py:88` 直接 `or "E:/Idea"`；`pdf_pipeline.py:93-94` 硬编码 `D:/AppData/model/...`。
- 09-20：`8611d8e`、`4f99e31` 继续收尾 E 盘字面量。

**→ v2 规则**：见 §3.2-R8——v2 把路径**集中**到了 `common.py` + canon（比 v1 散落是进步），但仍需"启动期校验 + 单源断言"。

---

#### D2. 产物根与备份根混乱

**证据（已验证）**：`work/.archive/` 下 30 个子项，记录了六轮布局变更：
- `BackupPaper-2026-08-09/08-10/08-11` 三个早期备份根命名不统一 → 09-20 全部归档。
- `BackupPaper-2026-W99-fake21B`（名字含 `fake21B`）→ **伪数据混入备份面**。
- `BackupPaper-opencode-residue`（`.gitignore` + `package.json`）→ **无关文件污染备份根**。
- `D-legacy-20260919`（Idea 262 文件 + 每周论文 47 + 论文备份 23）→ 迁移只复制不删除，D 侧留 legacy 副本。
- `D-datasets-legacy-20260920` → 曾把 204 条 claims 发布为 "3D Uncertainty Gap Dataset v1 (CC-BY 4.0)"，**与"止于 Idea 交付"的 scope 冲突**，被放弃。
- `D-papers-orphan-20260920` → 一份**关于本 OS 的论文草稿大纲**，属 scope 外（不写论文）产出。
- 备份 registry 的 `_note` 声称"repo keeps only this registry"，但磁盘实存 2 个 zip（218 MB + 48 MB）未被追踪——**声明与磁盘不符**。

**→ v2 规则**：产物根、交付根、备份根在 canon 中一次性定义，命名规则统一（`<root>/<slug>/`），禁止在根目录堆放批次性目录。备份面**只增不改**，且备份清单必须由程序生成、不手写。

---

#### D3. 沙箱/工具链环境事实（已固化的适配成本）

这些不是 v1 的设计错误，而是**必须写进 v2 环境契约**的事实（已验证）：

| 事实 | 影响 |
|---|---|
| `oc-research.ps1` 在 AI 会话内 **exit 0 但 stdout 为空**（沙箱吞输出） | 入口层必须能走纯 Python；PS 入口不可作为唯一通道 |
| 会话沙箱注入 `HTTP_PROXY`，访问 `localhost:23119` 得假 502 | 本地服务调用必须先 `--noproxy` / 清代理（v2 的 `disable_proxy_for_local()` 已对） |
| stdlib 默认证书池在本机无效 | 需代码内 certifi 兜底（v2 的 `ensure_ssl_cert_env()` 已对）；**用户级 SSL_CERT_FILE 已删，勿再写回** |
| MinerU 冷启动 ~42s，探针超时须 ≥120s | 能力探测不能设短超时（v1 曾因 30s 超时误判不可用） |
| GUI 进程活不过单条 Bash 命令 | Zotero 等 GUI 需后台长驻持有 |
| 跑全量 pytest 前需 `CODEBUDDY_SAFE_DELETE_ENABLED=0` | 沙箱 safe-delete 钩子会干扰 tmp 清理 |

**→ v2 规则**：把上表固化为 v2 的 `docs/ENVIRONMENT.md` 或 canon 的 `environment` 段，避免每个新会话重新踩一遍。

---

### E. 过程与方法论域（4 条）

---

#### E1. 用"堆功能"回应外部 repo 刺激 → 随后批量删除

**证据（已验证）**：
- 09-02 `4410509`：`full 8-item GitHub high-star optimization (MPQA+Planner+graph+evidence+index+skills+docling+novelty)`。
- 09-02 `53b68b4`：`full-marks L1 — 10 skills yaml...`。
- 09-03 `079d82f`：`32-repo borrow round2 — 43-cmd CLI registry, BGE GPU rerank service, MinerU service venv` ← **`uv.lock` 从 302 KB 一次性涨到 1.21 MB（×4）**。
- 随后：`52c254d`、`7c677ca`、`85dbd9d`、`f287d32`、`14ac969` 大批删除（cli_* / external_eval / conformal_gate / crossrun_memory / 10 个 skill / docling / qdrant）。
- 09-05 单日 **21 个提交**（全仓最高密度），紧接着是最大清理期。

**→ v2 规则**：外部能力只走 `borrow-not-merge` + JIT 触发表 + **硬验收**（v2 canon 的 `external` 段已正确吸收）。**没有当次任务需求的能力，不引入。**

---

#### E2. 报告产出速度 > 消费能力

**证据（已验证）**：`project-objective-review-20260905.md` 原文：「报告产出速度超过消费速度，存在**"为优化而优化"倾向**」；`outputs/archive/reviews-202609/` 一次性归档约 28 份评审/对标/重构文档，README 自评"未随代码演进更新"（已知过时点包括"oc_research_os.py 8k+ 行"已变 360 行）。

**→ v2 规则**：**每份报告必须绑定一个已执行的改动**。写而不用 = 负债。

---

#### E3. 无分支隔离，直接在线改生产

**证据（已验证）**：130 个 commit **全部在 `master`**，无任何 feature branch、无 stash。所有"弯路"直接发生在生产线上，回滚只能靠 revert/重冻结。

**→ v2 规则**：结构性改动（canon 改版、目录重构、机制引入/退役）走分支 + 验证后再合并。哪怕是一个人用，也要留这个缓冲带。

---

#### E4. 归档而非删除

**证据（已验证）**：反复出现"先归档、后删除"的两步走：`tools/_legacy_archive/`（8 天后删）、`tools/_deprecated_archive/`（11 天后删）、`tools/cli_*.py`（2 天后删）、`work/.archive/` 30 个子项（部分永久留存为历史包袱）。`work/.archive/` 的规则是"只移整目录，不删"。

**代价**：仓库内持续堆积"可能还有用"的东西，每次审计都要重新判断一遍。（v1 把 `work/` gitignore 掉，所以磁盘上 464 MB 里 `2026.9.4/pdfs` 单项就 153 MB。）

**→ v2 规则**：git 已提供历史。**删除就是删除**（`git rm`），需要保留证据时保留"文件名清单 + 删除理由"一行摘要即可，不保留内容副本。唯一例外：外部输入（研究者原始论文、标定数据）不归本仓管。

---

### F. 附：v1 最有价值的资产（v2 必须继承）

弯路之外，v1 有几件东西是**别处买不到的**，v2 已经部分继承，但要写实：

| 资产 | 价值 | v2 状态 |
|---|---|---|
| **单写者状态机 + 侧账 + reconcile** | v1 用真实故障（run 永久 blocked）换来的设计 | ✅ 已继承（`runs.py` 的 `add_paper`/`prescreen_append`/`reconcile`） |
| **LF 归一 + CRLF 变体容忍的冻结** | 30 天踩坑的最终答案 | ✅ 已继承 |
| **审计式重冻结（`--reason` + history）** | 唯一能让"事后补写"合法化的通道 | ✅ 已继承（`refreeze`） |
| **反模式卡（AP-01~05）** | 负面约束比正面提示有效 | ✅ 已继承（`knowledge/anti-pattern-cards.md`） |
| **canon 单真源 + identity sync 断言** | 治理核心 | ⚠️ 部分（断言只覆盖 Zotero 两项） |
| **permissions.json 真执行 + 无孤儿审计** | v1 后期才做对 | ✅ 已继承（且做得比 v1 早） |
| **`project-deep-review` 这种"十角度自查"方法** | 元层面的能力 | ➖ v2 尚未建立 |
| **Zotero 三段式人机接力流程** | 外部约束下的正确形态 | ⚠️ 骨架在，流程未固化 |

---

## 3. v2 现状诊断

### 3.1 已正确吸收（12 条，附代码位置）

| # | 吸收的教训 | v2 位置 |
|---|---|---|
| 1 | 单写者：`run.json` 唯一真源，ledger 是派生视图 | `pipelines/runs.py:100` `add_paper` docstring |
| 2 | 预筛走侧账，经 `reconcile` 由同一写入者晋升 | `runs.py:125` `prescreen_append` / `runs.py:144` `reconcile` |
| 3 | LF 归一 + CRLF 变体容忍 | `common.py:64` `sha256_file_variants`；`runs.py:222` |
| 4 | 审计式重冻结（reason 必填 + history） | `runs.py:231` `refreeze` |
| 5 | 空 run 守卫（≥2 active 阻止新开） | `runs.py:48-54` |
| 6 | 减速期 seeds 硬门豁免（`--supply-hold-reason`） | `runs.py:195` |
| 7 | canon 单真源 + identity sync 断言 | `pipelines/canon.py:27` |
| 8 | permissions 真执行 + 双向无孤儿审计 | `pipelines/permissions.py:46` |
| 9 | 交付分层，core 即完整 | `pipelines/idea.py:117,120` |
| 10 | 反馈回路 CLI（accept/reject/uncertain + reason 必填 + reject 写失败账本） | `pipelines/idea.py:63` |
| 11 | 可再生成物/产物/密码不进版本库 | `.gitignore` |
| 12 | 核心依赖最小化（3 个） | `pyproject.toml` |

### 3.2 已复发（10 条 —— **必须在写业务代码前修掉**）

> 严重度：🔴 = 现存 bug / 阻断级；🟠 = 高危复发；🟡 = 需清理。

---

**R1 🔴 策略数值双写复发（v1 用 5 轮才修好的病，v2 第 1 天就犯了 5 处）**

| 值 | canon 里的定义 | 代码里的副本 |
|---|---|---|
| L2 配额 10–15 | `deep_read.l2.quota_per_run: [10, 15]` | `runs.py:21` `L2_MIN, L2_MAX = 10, 15` |
| 语料门禁 3+1+1 | `idea.corpus_gate.{direct_fulltext:3, recent:1, counter_or_boundary:1}` | `idea.py:26` `need = {"direct_fulltext": 3, "recent": 1, "counter_or_boundary": 1}` |
| 6 维质量卡 | `idea.quality_card_6d: [...]` | `idea.py:15` `QUALITY_DIMS = (...)` |
| L3 双路径 | `deep_read.l3.paths: ["visual-critical","numeric"]` | `papers.py:10` `L3_PATHS = ("visual-critical","numeric")` |
| core-4 成员 | `idea.delivery_tiers.core: "4_files_complete"`（**没列名字**） | `idea.py:117` `CORE_FILES = (...)`（**且与 v1 的 core-4 定义完全不同**） |

`canon.check_identity_sync()` **只校验 Zotero 两项**，对这 5 处双写毫无察觉。这正是 v1 §A2/§A1 的复发起点——**双源一旦存在，漂移只是时间问题**。

**修法**：把 `L2_MIN/MAX`、`need`、`QUALITY_DIMS`、`L3_PATHS`、`CORE_FILES` 全部改为从 `canon.get(...)` 读取；把 `check_identity_sync()` 扩展为通用的"常量 ↔ canon"一致性断言（或直接删掉 `common.py` 里的常量副本，只留 canon 一份）。

---

**R2 🔴 两套互不兼容的路由枚举（现存 bug）**

- `runs.py:20`：`COVERAGE_ROUTES = ("direct", "counter_boundary", "transfer", "frontier")`
- `literature.py:14`：`DISCOVERY_CLASSES = ("direct", "counter", "boundary", "transfer")`

`finish()` 硬性要求 `coverage_route` 四路全部 > 0（`runs.py:187`），而 `literature.py` 产出的 `discovery_class` 用的是 `counter`/`boundary`。**`literature.DISCOVERY_CLASSES` 没有任何消费者（死代码），但它记录的是一套不同的词汇表**——一旦有人按它填 `coverage_route`，`add_paper` 会直接返回 `bad coverage_route`。

而 v1 的 canon 用的是第三套：`direct_evidence` / `transfer_bridge` / `counterevidence_boundary` / `frontier_radar`（`mechanized_retrieval.py` 的 CHANNELS，且 v1 已澄清那是**证据角色**不是检索源）。

**修法**：路由枚举在 canon 里定义一次（`coverage.routes`），`runs.py` 与 `literature.py` 都从它读；删除 `DISCOVERY_CLASSES` 或让它复用同一枚举。

---

**R3 🟠 canon 里搬回了 v1 已被证伪的机制**

| v2 canon 位置 | 内容 | v1 的结论 |
|---|---|---|
| `week_modes` | `2:2 per-run` 轮换 + `stall_cuts_early_hot_streak_extends_max_3_to_1` 自适应 | v1 DEC-0026/0027 就是这套；DEC-0025 已"去周化"，DEC-0035 进一步弱化 |
| `parallel` | `retrieval: 6, second_pass: 5, recognition: 4, deep_read: 4, idea_red_team: 5` | v1 正是这里反复调参然后撞 OOM：`retrieval 5->6, second_pass 4->5`（`776f37f`）→ `外层 4->1 worker 避双 CrossEncoder 并发 OOM`（`ac6c812`） |
| `runs.finish_gates.l2_quota: [10, 15]` | L2 配额设为**硬门禁** | v1 最大的返工源就是"全量 10-15"这类配额硬门 |
| `deep_read.templates` | `pre_reading_questions: 6` / `two_pass` / `assumption_ledger` / `figure_protocol_items: 5` | v1 DEC-0019 的 v3 模板，实测 47/151 应用率、`cold_recall` 零运行 |
| `claims_hub.views` | 3 个渲染视图 | v1 有 4 套视图（facts/matrix/gap-map/claims）且互相漂移 |
| `retrieval.living_queries` | `precision_window: 2` / `retire_below: 0.4` / `frontier_budget_cap: 0.34` | v1 同类参数（living queries precision 退役阈值）实际从未回填（DEC-0037：「LQ 314 条 entries 全 missing scores」） |

**修法**：对每一条，问"v1 用它成功过吗"。**没有成功记录的机制，默认不写进 canon**。特别是 `parallel` 的数值——v1 的教训是"并发数必须由实测压出来"，写死数字等于预设了一个没验证的结论。

---

**R4 🔴 `verify_freeze` 里的死代码（v1 §B7 同型复发）**

```python
# runs.py:267-268
void = dict(canon.load()).get("runs", {}).get("freeze", {})
_ = void
```

写出来又不用，`canon` 被 import 只为这一行。v1 的 DOA 模块（`arxiv_html_meta.py`/`claims_append.py`）就是这种习惯的产物。

同类：
- `validate.py:68-69`：`if strict and warnings: pass` —— 空操作。
- `pipelines/papers.py`：**整个模块没有任何 CLI 命令入口**（`cli.py` 里没有 papers 相关 subcommand），是半孤儿。
- 顶层 `integrations/`、`delivery/` 两个**空目录**。

**修法**：全部删除或接线。

---

**R5 🟠 悬挂 active run 已出现（v1 高频坑）**

`runs/weekly/WEEKLYRUN-20260920-120000/run.json` 状态 `active`、`paper_candidates: []`、`coverage` 全 0、`report.md` 内容为 `> attempt 1 — fill on finish.`。这是 16:25 手工测试的残留（v1 的 `TEST-PYTEST-run-094943`、66 个空 run、`WEEKLYRUN-20260913-151819` 同型）。

而且它会**实际影响行为**：`runs.start()` 的守卫是"≥2 个 active 才拦"，这一个已经让计数为 1。

**修法**：删掉它，并在 `validate` 里加"active run 超过 24h 未更新即告警 / active 且 papers=0 即报错"。

---

**R6 🟠 测试隔离是"手动 patch 模块常量"，没有仓库污染守卫**

v2 现在的方式（`test_freeze.py:16`）：
```python
monkeypatch.setattr(runs, "WEEKLY_ROOT", tmp_path)
```
问题：`WEEKLY_ROOT` / `IDEA_ROOT` / `POOL_PATH` / `FEEDBACK_PATH` / `FAILURE_PATH` / `DELIVERY_ROOT` / `QUEUE_ROOT` / `CLAIMS_PATH` 是 **8 个分散在不同模块的模块级路径常量**，必须逐个记住 patch。新增一个忘了 patch 就直接写真实仓库——**这正是 v1 被污染 8 次、2395 个文件的机理**。

而且 `tests/conftest.py` 只有 4 行（仅 `sys.path`），**没有 v1 最后做出来的那道防线**：
- session-scoped autouse fixture：首尾快照 `git status --porcelain`，非空即 fail；
- 所有输出根环境变量化（v1 的 `OC_STATE_PATH` / `OC_WEEKLY_RUN_ROOT` / `OC_IDEA_DELIVERY_ROOT` …）；
- legacy 路径哨兵。

**修法（直接照搬 v1 的成熟方案）**：
1. `common.py` 所有路径常量改为 `Path(os.environ.get("IDEAOS_XXX", default))` 形式；
2. `conftest.py` 加 session autouse fixture，**同时**在会话开始前把全部输出根重定向到 `tmp_path_factory` 的会话目录；
3. 加"仓库污染守卫"：会话前后 `git status --porcelain` 对比（v2 需要先有 git，见 R7）。

---

**R7 🔴 没有版本控制（最严重）**

`D:\AppData\Project\Idea` **没有 `.git`**。

**代价**：v1 最有价值的资产就是那 130 个 commit（可追溯、可回滚、可考古、可 blame）。没有 git：
- 无法回滚任何结构性改动；
- 无法用 `git status` 做污染守卫（R6 依赖它）；
- 无法追溯"某条规则为什么变成这样"；
- 与 v1 的 `85dbd9d`/`34fc4ba` 那种"整批删除"操作无从审计。

同时缺失：`.github/workflows`（CI）、`.pre-commit-config.yaml`。

**修法**：**第一件事就是 `git init` + 首次提交**，之后所有改动走提交。CI 至少跑 `pytest` + `ruff check`。

---

**R8 🟠 绝对路径仍进仓（只是从"散落"变成了"集中"）**

- `common.py:22-25`：`DELIVERY_ROOT = Path("E:/Idea")`、`PAPER_ROOT`、`PAPER_MIRROR_ROOT`、`FORBIDDEN_INPUT_ROOTS = (..., "C:/Users/User/Documents/3D重建科研")`。
- canon `identity`：`E:\\Idea`、`E:\\Paper`、`E:\\Backup\\Paper`、同一用户目录。

集中化是好进步（v1 散在 43 处），但**仍在代码里**，且 `check_identity_sync()` **不校验路径**（只校验 zotero 两项）。

**修法**：
1. 路径全部走环境变量/配置，代码里只留"未设置即报错"的显式失败；
2. `check_identity_sync()` 扩展到路径；
3. CI 加一条：`grep -rn "E:\\\\|D:\\\\|C:\\\\" pipelines/ governance/` 命中即失败（v1 的教训是"任何 commit 不允许出现盘符字面量"）。

---

**R9 🟡 半成品痕迹**

- `knowledge/gap-map.md` / `living-queries.json` / `feasibility_profile.json` 是从 v1 抄来的**占位**（`种子待收口`、`lab: 光电学院（平均画像）`），不是真实数据。
- `knowledge/anti-pattern-cards.md` 只有 5 张卡（v1 到后期是 AP-06/07/08 更多）。
- `idea.publish()` 写入的是占位模板（`f"# {slug}\n\n> tier={tier} · {name}\n"`），不是真交付物。
- `delivery/`、`integrations/` 空目录。
- `pipelines/__pycache__/` 里同时有 **cpython-310 与 cpython-314** 两种 pyc（且 `.gitignore` 已排除 `__pycache__/`，所以只是磁盘脏）。

**修法**：占位内容要么填实要么删除；空目录删掉；`.pyc` 清掉。

---

**R10 🟡 入口层仍是 PowerShell + 若干设计小摩擦**

- `os.ps1` 存在，README 首推 `.\os.ps1 session-brief`。v1 已验证：**在 AI 会话内 PS 入口 exit 0 但 stdout 为空**。若未来会话照 README 执行，会得到"命令成功但无输出"的假象。建议 README 首推 `python cli.py`，`os.ps1` 只作人工便利。
- canon 说 `AGENTS.md` 第 8 条"RAG/向量 dormant"，但 `pyproject.toml` 保留 `vector = ["chromadb>=0.4"]` extra。v1 的 qdrant 就是"声明了但从未安装"的幽灵依赖。
- `pipelines/claims.py` 同一文件两种写模式：`append_claim` 追加，`record_verdict` **全量重写**（并发不安全、顺序可能变）。v1 的 `state.json` 全量重写模式已被判为弱点。
- `pipelines/idea.py` 的 pool 是单个 JSON 数组，每次 `add_candidate` 全量重写。
- `validate.py:8` `REFERENCED_ACTIONS` 是**手工维护的元数据集合**，与代码实际调用靠人工同步（新增调用点忘了加 → 误报 "action without policy"）。
- `zotero.check_no_hardcoded_root` 只匹配字面量 `"opencode/"`，本质是"防上一次的具体 bug"，不是通用机制（换一个集合名就失效）。

**修法**：逐一收敛。特别是 `record_verdict` 的写模式与 `REFERENCED_ACTIONS` 的手工同步。

### 3.3 v2 尚未覆盖（6 条）

| # | 缺失 | v1 的对应资产 | 为什么必须补 |
|---|---|---|---|
| 1 | **版本控制 + CI + pre-commit** | v1 130 commits + `.github/workflows/research-os.yml` | 见 R7 |
| 2 | **仓库污染守卫** | v1 `conftest.py` 的两道 session autouse fixture | 见 R6；这是 v1 用 8 次污染换来的 |
| 3 | **备份机制与前置检查** | v1 `backups/registry.json` + "7 天内必须有新备份"（`common.py:274`） | `permissions.json` 里 `modify_project`/`zotero_write` 声明了 `allow_with_recent_backup`，但**没有任何代码校验备份新鲜度**——`permissions.check` 直接返回 `Decision(True, "backup freshness must be verified by caller")`（`permissions.py:38`），把责任推给了一个不存在的 caller。**这是当前的"假严格"**（v1 有过同型问题：`permissions.json` 无 reader） |
| 4 | **存量反馈消化机制** | v1 `outputs/idea-feedback-queue.md` + `supply_policy` | v2 AGENTS 第 5 条写了"28+ 存量 verdict 回填优先"，但 v2 的 pool 是空的（`knowledge/candidate-pool.json` 不存在），机制无处落地。需明确存量从哪来（v1 的 29 个 `E:/Idea/*/researcher-decision.json`） |
| 5 | **交付卫生检查** | v1 DEC-0032 `publish_hygiene` 三条规则 | v2 `idea.publish` 只做了"目标目录非空即拒绝"，没有 slug 合法性、absorbed 判定、测试根隔离 |
| 6 | **文档腐烂防护** | v1 教训（AGENTS/README 滞后、快照腐烂） | v2 的 README/AGENTS 目前很短所以还没腐烂，但没有任何机制阻止它腐烂 |

---

## 4. v2 设计硬规则（可直接执行）

按"必须先做"排序。每条给出**验收方式**——做不到验收的规则不要写进 canon（§A5）。

### 组 1：单真源（治 A1/A2/A3）

| # | 规则 | 验收方式 |
|---|---|---|
| G1.1 | **一个 canon 文件**。禁止 shim / 镜像 / 分片 / "指针层"。 | `find governance -type f` 只有 `workflow_authority.json` + `decisions.json` + `permissions.json` |
| G1.2 | **任何策略值在 Python 里不得有字面量副本**，一律 `canon.get("..."）`。 | 写一个测试：扫描 `pipelines/*.py`，对 canon 中所有数值/枚举类叶子做"字面量出现次数 == 0"断言 |
| G1.3 | **常量同步断言必须覆盖全部，不是抽样**。`check_identity_sync` 改为遍历 `common.py` 中声明的所有常量。 | 故意改 canon 一个值，测试必须失败 |
| G1.4 | **文档不得复述数值**。AGENTS/README 只写"见 canon#xxx"。 | CI grep：文档中出现 canon 里的数值字面量即失败 |
| G1.5 | **上下文注入实时生成，禁止落盘快照**。 | 无 `*snapshot*.json` 被 commit（备份清单除外） |

### 组 2：边界与隔离（治 B3/B4/B5/R6/R7）

| # | 规则 | 验收方式 |
|---|---|---|
| G2.1 | **git init 先于一切**；所有改动走提交；结构性改走走分支。 | `git log --oneline` 非空 |
| G2.2 | **所有输出根走环境变量**，默认值仅作便利，且启动时校验存在性。 | 设一个不存在的 `IDEAOS_DELIVERY_ROOT`，命令必须显式报错而非静默空转（v1 的 `RESEARCHER_SCAN_ROOT=E:\论文` 静默空转） |
| G2.3 | **测试默认隔离**：conftest 在 session 开始前把全部输出根重定向到 tmp。 | 删掉任何单测里的 `monkeypatch.setattr(..., PATH, ...)` 路径 patch，测试仍全绿 |
| G2.4 | **仓库污染守卫**：session 首尾 `git status --porcelain` 必须一致。 | 故意加一个写真实仓库的测试，守卫必须让它 fail |
| G2.5 | **产物不进版本库**：crops / PDF / zip / 缓存 / 备份。 | `.gitignore` 已对；加 `git status` 复查 |
| G2.6 | **单文件体积上限由 CI 强制**（v1 的 8500 行规则形同虚设）。 | 设一个明确上限（如 600 行），超限即 CI 红 |
| G2.7 | **无真锁**。每个状态文件只有一个写入者；跨进程写同一文件视为设计缺陷。 | 无 `lock` 相关代码 |

### 组 3：门禁哲学（治 A4/C1/C2/C3）

| # | 规则 | 验收方式 |
|---|---|---|
| G3.1 | **只保留证据充分性硬门禁**（标识符、二次验证、撤稿、交付文件齐备）。 | canon 中 `hard` 只出现在这几类 |
| G3.2 | **配额类/覆盖类/日历类一律 soft**。 | canon 中无 `quota`/`coverage` 类 hard |
| G3.3 | **门禁必须能被豁免且豁免要留痕**，禁止"卡死无法收口"。 | 每个 hard 门都有一个显式豁免参数 + 写入 `uncertainty_disclosure` |
| G3.4 | **门禁自身要有测试**。v1 的 `validate --strict` 自己坏了（freeze 时序 bug）→ "门禁还需要门禁"。 | 每个门禁有正例 + 反例测试 |
| G3.5 | **反馈覆盖率是首屏数字**。 | `session-brief` 输出含 `feedback.coverage` |
| G3.6 | **供给受反馈覆盖率约束**：coverage < 50% 时不得新增候选。 | `idea.add_candidate` 在低 coverage 时返回 warning 或拒绝 |

### 组 4：过程纪律（治 E1~E4/A5/B6/B7）

| # | 规则 | 验收方式 |
|---|---|---|
| G4.1 | **引入外部能力 = borrow，不 merge**；必须有当次任务需求 + 端到端验收。 | 每个外部依赖在 canon `external` 里有一条触发条件；无触发的依赖不得出现在 `pyproject.toml` |
| G4.2 | **禁止 `--help OK` 式验收**。 | 新能力必须有产出正确结果的测试 |
| G4.3 | **never-landed 直接删，不归档**。 | 无 `_deprecated_archive/` 类目录 |
| G4.4 | **不建宿主已有的能力**。 | 新增子系统前在 commit message 里写"宿主为什么不能做" |
| G4.5 | **每份报告绑定一个已执行改动**。 | 报告目录中无"纯分析无行动"的孤立文件 |
| G4.6 | **新增 canon 规则必须同时落一个能失败的测试**。 | 规则条目与测试文件互相可追溯 |
| G4.7 | **回收期检查**：每次 session-brief 报告"规则总数 vs 近两周实际被触发的规则数"。触发率为 0 的规则进入退役候选。 | 该数字出现在 session-brief |

### 组 5：环境契约（治 D1~D3）

| # | 规则 | 验收方式 |
|---|---|---|
| G5.1 | **环境事实固化**（§D3 那张表）到 `docs/ENVIRONMENT.md`。 | 文件存在且被 README 引用 |
| G5.2 | **代码内 SSL 兜底**（不用用户级环境变量）。 | 已做对（`ensure_ssl_cert_env`） |
| G5.3 | **本地服务调用先清代理**。 | 已做对（`disable_proxy_for_local`） |
| G5.4 | **能力探测超时 ≥ 冷启动时间**。 | 如 MinerU ≥120s |
| G5.5 | **AI 会话入口优先纯 Python**；PS 入口不得作为唯一通道。 | README 首推 `python cli.py` |

---

## 5. 实施路线

### P0 —— 在写任何业务代码之前（今天内）

1. **`git init` + 首次提交**（R7）。
2. **删除 `runs/weekly/WEEKLYRUN-20260920-120000`**（R5）。
3. **修 R1（数值双写）与 R2（路由枚举矛盾）**——这两条是现存 bug，且是 v1 花 5 轮才修好的病。
4. **删死代码**：`runs.py:267-268`、`validate.py:68-69`、空目录 `delivery/` `integrations/`、`__pycache__`（R4/R9）。
5. **修 R6（测试隔离）**：路径环境变量化 + conftest 全局重定向 + 仓库污染守卫。
6. **修 §3.3-3（备份前置检查的"假严格"）**：要么真正实现备份新鲜度校验，要么把 `allow_with_recent_backup` 降级为普通 allow 并删掉误导性语义。

### P1 —— 骨架定型（本周）

7. 重审 canon：把 R3（并行数值、week_modes、L2 硬配额、v3 模板）逐条按"v1 成功过吗"过滤。
8. 补 §3.3-1/2（CI + pre-commit）：`pytest` + `ruff` + 盘符字面量扫描 + 文档数值扫描。
9. 补 §3.3-5（交付卫生）与 §3.3-6（文档腐烂防护）。
10. 固化 `docs/ENVIRONMENT.md`（G5.1）。
11. 建立"回收期检查"（G4.7）：session-brief 输出规则触发率。

### P2 —— 业务铺开前

12. 明确存量反馈来源（v1 的 29 个 `researcher-decision.json`）与回填流程（§3.3-4）。
13. 真实 gap-map / living-queries / feasibility_profile 数据落位（R9）。
14. 建立"十角度自查"方法（v1 的 `project-deep-review` 模式），作为每个里程碑的固定动作。

---

## 6. 附录：证据索引

### 关键 commit（v1，按主题）

| 主题 | commits |
|---|---|
| 哈希/parity 死循环 | `0340b1a` `2468504` `d72cbd2` `5d8ac8f` `b967b83` `153d4a8` `e2d7cb4` `473f381` `318f162` `efa8faf` `42b3a17` `79825bc` `bd88f83` `e5843d7` |
| parity 机制退役 | `34fc4ba` |
| 测试污染 | `07dadab` `758ba1d` `6feb4b5` `a378a17` `fb5e56e` `734e5d5` `284f1ed` |
| 规则 shim 化 | `9cf92e7` `f36d814` `051e1a4` `a64484f` `3ccf864` `79825bc` `59456d4` |
| 90min 残留 | `3e55930` `a64484f` `2938d6f` |
| 神文件拆分 | `a64484f` `d736df9` `e6d8fa0` `52c254d` `d01a138` |
| 外部 repo 激进入侵 | `4410509` `53b68b4` `079d82f` `20c66c4` |
| 批量删除 | `52c254d` `7c677ca` `85dbd9d` `f287d32` `14ac969` `0bf00c5` `0bf00c5` |
| Zotero | `52f0f61` `c44bf67` `72b4505` `fc6d288` |
| 路径/迁移 | `2903b23` `92a2542` `8611d8e` `4f99e31` |
| 去周化/节律 | `df62667` `8692b05` `c7d1d07` `34fc4ba` `58f16d1` `c0581ad` |

### 关键文件（v1）

- 自审报告：`outputs/project-audit-2026-09-05.md`、`project-objective-review-20260905.md`、`-r2.md`、`project-deep-review-20260914.md`、`project-path-ownership-and-parity-review-20260920.md`、`legacy-cleanup-2026-09-05.md`、`skill-integration-map-20260905.md`、`github-benchmark-2026-09-13.md`、`idea-verification-report-20260905.md`、`idea-pool-triage-proposal-20260905.md`、`project-environment-adaptation-checklist-20260919.md`
- 归档：`outputs/archive/`、`outputs/archive-2026-08-21/`、`work/.archive/`（30 子项）
- 治理：`oc-research-os/governance/{workflow_authority.json, decisions.json, permissions.json}`、`AGENTS.md`
- 代码：`tools/core/{runs.py, common.py, validate.py}`、`tools/mechanized_retrieval.py`、`tools/zotero_ui_import.py`
- 环境事实：`.workbuddy/memory/MEMORY.md`

### 新仓（v2）被点名的位置

| 问题 | 位置 |
|---|---|
| 数值双写 | `pipelines/runs.py:21`、`pipelines/idea.py:15,26,117`、`pipelines/papers.py:10` |
| 路由枚举矛盾 | `pipelines/runs.py:20` vs `pipelines/literature.py:14` |
| 死代码 | `pipelines/runs.py:267-268`、`pipelines/validate.py:68-69`、`pipelines/papers.py`（无 CLI 入口） |
| 悬挂 run | `runs/weekly/WEEKLYRUN-20260920-120000/` |
| 测试隔离不足 | `tests/conftest.py`（仅 4 行） |
| 无 git / CI | 无 `.git`、无 `.github/`、无 `.pre-commit-config.yaml` |
| 绝对路径 | `pipelines/common.py:22-25`、`governance/workflow_authority.json#identity` |
| 假严格 | `pipelines/permissions.py:37-38` |
| 空目录 | `delivery/`、`integrations/` |
| v1 已证伪机制搬回 | `governance/workflow_authority.json` 的 `week_modes` / `parallel` / `runs.finish_gates` / `deep_read.templates` |

---

*本报告所有量化结论均有命令输出或文件内容佐证；仅 D2 中 `BackupPaper-2026-W99-fake21B` 的命名含义未证实。*
