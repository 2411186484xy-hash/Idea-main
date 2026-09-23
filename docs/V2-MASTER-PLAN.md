# V2 终极建设方案 v2.1（2026-09-23）

> 输入：本次审计证据包（`.workbuddy/memory/audits-2026-09-23/`）——V1 只读审计 ×5（retrieval / zotero / deepread / idea / docs，全部带 file:line 引证）+ GitHub 生态调研 ×2（检索源与 Zotero 生态、idea 生成生态，2026-09-23 API 实测快照）+ 源可达性实测（probe×2）。
> 承接：`docs/FOUNDATION-DESIGN.md` v2.0（哲学与根原则不变）· 本文件 v1.2 的已执行部分（M0–M2i + 首轮 e2e）· 用户 2026-09-23 六项增量诉求。
> 总原则（不变）：**V1 用"再加一层机制"解决的问题，V2 删掉问题的来源**；凡声明的能力当天有消费方 + 能失败的测试；**一次性执行，执行期内不新增范围**（发现的缺口记入 §9，不临场扩展）。

---

## 0. 现状判定（全部为 2026-09-23 实测）

**已执行**：M0 端口式重写 · M1 治理定型（1.1–1.8）· M2a–M2i 全部落地 · P1.1/P1.2 · 首轮端到端 run（`c9b3b7f`：38 claims / 16 papers / Zotero 写入+回读归档 / idea `region-availability-gate-single-shot-sl` 交付 / 研究者 accept verdict）。

**基线数字**（计划时快照）：pytest 135 passed · 代码 2582/4000 行 · 测试 1807/3000 行 · canon 119/200 行 · 21 命令 · search.py 299/300 行（贴顶）。

**本次实测新发现（须在本版处置）**：

| # | 发现 | 证据 |
|---|---|---|
| F1 | `feedback.jsonl` 与 `session-log.jsonl` 各含 2 条重复行（同 slug / 同 run_id） | `knowledge/*.jsonl` 实测；validate 目前不检测重复 |
| F2 | `knowledge/.cache/` 未列入 .gitignore（`??` 常驻工作区） | `git status` 实测 |
| F3 | canon/code 引用 `V1-RETROSPECTIVE.md`、`legacy-detours.md` 均不在 v2 仓（悬空引用） | grep 命中 governance/、docs/FINAL-REPORT、pipelines/feedback.py |
| F4 | candidate 的 `sources` 溯源轨迹不在契约内：search 输出的 `sources` 字段传给 paper-add 会被契约判 `unexpected keyword` | search.py `_dedup` vs contracts.PaperCandidate |
| F5 | 新源可达性（本机实测）：DOAJ 200/1.3s 稳 · OpenReview api2 200/1.1s（笔记需按 title 过滤）· DBLP 可达但突发 429（需 ≤1req/s+退避）· S2 退避后 200 但**无摘要** · OpenCitations 200 但 28.7s 慢 · Unpaywall 200/5.0s · bioRxiv 仅 details-by-DOI（无关键词检索） | `.workbuddy/memory/audits-2026-09-23/probe_sources*.py` 输出 |

---

## 1. 六项增量诉求 → 裁决总表

| # | 用户诉求 | 裁决 | 落点 |
|---|---|---|---|
| R1 | 检索源极其广泛 | ACTIVE 5 源 + 按需 2 源 + 引文扩展（全部本机可达实测），并给出"新源接入协议"扩展接口 | §2、W1 |
| R2 | 自动化程度极高 | 批量和并发：paper-add/claims-add 批量模式、多源并发扇出、pdf-fetch 自动获取 OA 全文；认知边界不自动化 | §6、W1/W5 |
| R3 | 高质量深度文献 | 页作用域 quote 硬 lint（真校验而非字段存在性）+ PDF 完整性门 + 页渲染目检 + OA 抓取 | §3、W2 |
| R4 | 与 Zotero 高度联动、补插件空缺 | 三段式已有 + 主题标签 + claims→笔记草稿（CONFIRMED 才入）+ 插件互补矩阵文档化 | §4、W3 |
| R5 | 完美的 idea 生成 | novelty 三态（零命中≠新颖）+ 失败账本硬拦 + 碰撞库内嵌 + disproof 设计件 + 质量卡盲评 | §5、W4 |
| R6 | 检索主题可扩展 + 跨领域方法检索路线 | `knowledge/topics.json`（扩展接口，加主题=加数据）+ transfer 桥接查询族（其他领域新方法→本方向） | §2.2/§2.3、W0/W1 |

---

## 2. 检索扩展（R1 + R6）

### 2.1 源矩阵（全部 2026-09-23 本机实测）

| 源 | 层级 | 实测 | 摘要 | 用途 |
|---|---|---|---|---|
| OpenAlex | ACTIVE | 在用，polite pool | 有（倒排还原） | 主检索 + 引文扩展 |
| arXiv | ACTIVE | 在用，3s 间隔 | 有 | 预印本（物理/CS/方法迁移主战场） |
| Crossref | ACTIVE | 在用 | 部分 | 出版元数据 + 撤稿通道 |
| Europe PMC | ACTIVE | 在用 | 有（core） | 生命医学（内窥镜近邻） |
| **DOAJ** | ACTIVE（新） | 200 / 1.3s | 有 | OA 期刊，补非主流出版社覆盖 |
| **DBLP** | 按需（新） | 可达；突发 429 | 无 | CS/ML/医学影像会议（MICCAI/CVPR/ICCV…），transfer 路线主源 |
| **OpenReview** | 按需（新） | 200 / 1.1s | 有（笔记筛选后） | ICLR/NeurIPS/ICML 投稿与评审（最新方法前沿） |
| 引文扩展 | 新能力 | OpenAlex 实现 | — | `search --expand <doi>`：前向 cited_by + 后向 references（替代 V1 两跳 citation_track，压到 ~40 行） |

**明确不引入**（每条都有 why，防"对标堆料"）：
- **PubMed / Lens**：研究者 2026-09-20 裁决弃用，勿再提议（`work/.archive/env-legacy-20260920`）。
- **Semantic Scholar**：退避后可用但**无摘要**（Springer 协议），与 OpenAlex 覆盖高度重叠 → 不引入，避免堆料。
- **OpenCitations**：28.7s/请求过慢，引文关系由 OpenAlex expand 覆盖。
- **Google Scholar 抓取 / Sci-Hub**：ToS 与合规红线。
- **CORE**（需 key）、**OSF/HAL/OpenAIRE**（覆盖重叠，probe 通过但不引入）、**bioRxiv API**（无关键词检索，仅 details-by-DOI，不构成检索源）。
- **docling/MinerU 第二解析通道**：无消费证据前不引入（V1 docling"从未落地"教训）；文本层 + 页渲染足够支撑页锚 claims。

### 2.2 检索主题扩展接口（R6 核心）——`knowledge/topics.json`

单一真源、研究者可扩、validate 强校验（schema 严格：未知键即拒）。加一个检索主题 = 加一条数据，**零代码改动**：

```json
{ "schema_version": 3, "topics": [ {
  "id": "single-shot-sl", "name": "单帧结构光三维重建", "status": "active",
  "problem": "单帧条纹深度重建的精度与可靠性保证",
  "key_terms": ["fringe projection", "single-shot", "phase demodulation"],
  "target_domains": ["structured light 3D", "fringe projection profilometry"],
  "frontier_domains": ["conformal risk control", "event-based vision", "implicit neural representations"],
  "transfer_pairs": [
    {"from_field": "ML uncertainty", "method_terms": ["conformal prediction", "distribution-free coverage"], "to_problem": "深度可靠性保证"},
    {"from_field": "neuromorphic vision", "method_terms": ["event camera"], "to_problem": "高速单帧采集"} ],
  "negative_terms": ["structured-light-free"],
  "anchor_papers": ["doi:10.1364/..."],
  "venues": ["CVPR", "MICCAI", "Optics Express", "IEEE TIM"]
} ] }
```

- 消费方：`query-brief --topic <id>`（四路由 + transfer 桥接族）、`idea-brief --topic`（碰撞源域抽自 frontier/transfer）、`run-start --topic`、`session-brief`（活跃主题一行）。
- 扩展接口之二 = **新源接入协议**：一个适配器函数（sources.py）+ 一条 canon 条目（active/available + why）+ 离线解析测试 + smoke 真记录测试；`test_sources` 断言 canon 所列与代码注册表双向一致（声明==实现）。

### 2.3 跨领域方法检索（"其他领域新方法"检索路线）

- `transfer` 路由由"查询后缀"升级为**结构化桥接族**：对每条 `transfer_pairs` 生成 `{method_terms} × {target_domains}` 跨域查询，定向投放 DBLP/OpenReview/arXiv（cs/ML venue），命中候选标记 `discovery_class=transfer`。
- 与碰撞库（§5.3）打通：transfer 检索结果 = 碰撞提示包的现实锚，防止"凭空碰撞"。

### 2.4 search 增强

- `channel_health` 三态输出（ok / empty / error）——"零召回 ≠ 真空"（V1 LST:840-851 教训）：空结果与失败在输出上可区分，失败进 ErrorEnvelope。
- 摘要 600 字截断（V1 `literature_search_tools.py:1067` 语义回归，保 run 文件有界）。
- **并发扇出**：多查询 × 多源改线程池（≤4 workers，canon `search.max_concurrency`）；arXiv 3s 间隔与 per-host 礼貌保持；结果确定性排序。多查询串行 ~30s → ~8s。
- 拆分模块 `pipelines/sources.py`（传输 + 全部适配器 + 注册表；search.py 保留调度/去重/健康/扩展）：两文件都回到 300 行红线内（search.py 现 299，已贴顶）。

---

## 3. 深读质量（R3）

| 项 | 内容 | 依据 |
|---|---|---|
| 页作用域 quote 硬 lint | `claims-add` 真校验：quote 空白归一后必须命中 `page_anchor` 页文本（±1 页边界容差），否则**拒绝**；文本来自 `pdf-extract --run --paper-key` 缓存的 `runs/<id>/text/<safe_key>.json` | V1 deepread_lint 全篇匹配过松教训（audit-C §5）；v2 现仅校验字段存在性 |
| PDF 完整性门 | `%PDF` 魔数 + `%%EOF` 尾标 + ≥100KB（canon `pdf.min_bytes`）+ 失败即明确信封 | V1 LST:1770-1818/1935，v2 完全缺失（audit-A #3） |
| 页渲染目检 | `pdf-extract --render <page>` 出 PNG 到 `runs/<id>/renders/`（git 排除），供会话模型对数值/图依赖 claim 目检；**不承诺**表格/公式自动抽取 | V1 `visual_verified` 自证教训（audit-C #4）：没有真看图就不许声称"视觉已核" |
| OA 全文抓取 | 新命令 `pdf-fetch`：Unpaywall(mailto) → arXiv pdf → Europe PMC OA 全文 → `D:\Research\Paper\_inbox\<paper_key>.pdf`；全败如实信封，无兜底渠道（Sci-Hub 永不） | V1 PDF 瀑布精简版（砍 arxiv-lib/MDPI/校网，audit-C 处置）；R2 自动化 |
| 深读任务书 | writer/verifier 盲分离已有（保留）；verifier 书附"数值精确模式"：数字必须逐字符匹配（禁四舍五入） | citation-check-skill 两遍法（survey-F，MIT 借鉴） |

---

## 4. Zotero 深度联动与插件互补（R4）

**已有且保留**：本地 API 读（免 key、无速率限制）· 三段式 manifest→写→回读审计（行业空白能力，54yyyu/cookjohn 两个 MCP 均无回读）· `idea-os:<paper_key>` 稳定标签。

**本版新增**：

1. **主题标签**：run.topic 存在时清单条目追加 `idea-os:topic:<topic_id>`（canon `zotero.tag_prefix`），使 Zotero 内可按研究主题过滤——这是 v2 检索主题体系在 Zotero 侧的投影。
2. **claims → 笔记草稿 `zotero-notes`**：从 run 内 **仅 CONFIRMED** claims 生成逐篇 `note.md`（逐字引用 + `(p.N)` 页锚 + claim id），写 `D:\Research\Paper\library\<paper_key>\note.md` 并镜像 SHA 一致；经 Better Notes 手动导入 Zotero（半自动通道边界，audit-B 教训）。
3. **插件互补矩阵（README 一节，数据面契约）**：

| 互补位 | 现状（插件/MCP） | v2 提供 |
|---|---|---|
| 写入回读审计 | 无（fire-and-forget） | manifest+SHA+readback 归档 |
| claims 笔记 | 无 | 页锚笔记草稿（CONFIRMED 才入） |
| 主题/角色标签 | Reading List 仅 3 状态标签 | `idea-os:*` 受控命名空间（不动插件标签） |
| 我们复用的插件数据面 | — | BBT citekey（DOI 齐备即可生成）· Better Notes markdown 导入 · Attanger/Zotmoov 管附件路径（我们不碰）· Green Frog 管 Extra 分区（我们不写）· PDF Translate 管翻译（quote 须原文逐字，翻译会破坏锚定，故不依赖） |

---

## 5. idea 质量与反馈闭环（R5）

1. **novelty 三态**（零命中≠新颖；V1 22/22 假 novel 教训）：`novelty_log` 条目必填 `result ∈ {hit, empty, error}` 与 `confidence ∈ {strong, weak}`（会话生成=strong，模板回退=weak）；全部 empty 时 idea-add 要求 screening_note 记录"零命中已降级为 reach 不足"；`top_match` 仅在 hit 时必填。
2. **failure-ledger 硬拦**：生成前 `idea-brief` 注入教训（已有）+ `idea-add` 对 title 做双阈值近似拦截（canon `ideas.avoidance`：token overlap ≥4 或 ≥3 且 jaccard ≥0.40 → 拒绝并指向账本行）+ 领域泛化停用词表（V1 `core/idea.py:465-568` 唯一有实证迭代痕迹的规则，含 R1C2 反例）。
3. **碰撞库内嵌**：`knowledge/collision-bank.json`（~15 条 `{domain, principle, template}`，取自 V1 `idea_collision.py` DOMAIN_BANK 精选）；`idea-brief` 缺省源/目标域时按 seed 确定性抽样——**不再有独立 CLI/落盘目录**（V1 落地 13 天零消费的教训：提示包必须直接内嵌生成步骤）。
4. **disproof 设计件**：`IdeaCandidate.disproof` 四字段必填 `{experiment, controls, decision_rule, failure_interpretation}`；publish 渲染 `disproof.md`（纯设计文本，**不含可执行 scaffold**——V1 空壳桩"生成即跑不过"教训）。
5. **质量卡盲评**：`idea-brief` 附 verifier 书——对 6 维卡盲重打分，任一维分歧 ≥2 分提示修订（reviewer.py 证据绑定评分的会话版）。
6. **重复回落修复**：finish 幂等（session-log 已有 run_id 即拒）+ feedback 精确重复拒绝 + validate 检测两类重复（F1）。

---

## 6. 自动化与命令面（R2）

- `paper-add --batch <file.json>` / `claims-add --batch <file.json>`：逐条过门禁、汇总报告、幂等不变（会话模型一次供 N 条，替代 N 次调用）。
- 并发扇出（§2.4）；`pdf-fetch` 自动 OA 全文（§3）。
- **自动化边界（如实声明）**：认知判断（择选/核查/生成）永远在会话内；Zotero 写入的首授权是研究者一次性交互；研究者 verdict 是唯一非自动信号——三者**设计上不自动化**。
- 命令面 21 → 23（+`pdf-fetch`、+`zotero-notes`）；README 命令表与 test_docs 同 commit 更新。

---

## 7. 执行波次（W0→W6；每项 = commit 粒度，带验收）

**W0 地基修订**（分支 `v2.1`）
- 0.1 契约增量：`PaperCandidate.sources[]`（F4，source-tracking 落契约）· `Run.topic` · `IdeaCandidate.disproof` · `novelty_log` 三态字段（加法式、默认值兼容，schema_version 不升）→ contracts 净增 ≤18 行（同步压缩既有注释，守 300 红线）。
- 0.2 数据修复：F1 重复行去重（feedback/session-log 各保留一条）· F2 `.gitignore` 加 `knowledge/.cache/` · F3 悬空引用清扫（canon/code 的 `V1-RETROSPECTIVE`/`legacy-detours` → 指向 `.workbuddy/memory/audits-2026-09-23/` 或 V1 只读仓）。
- 0.3 幂等守卫 + validate 重复检测（§5.6）。
- 0.4 `knowledge/topics.json`（首条：单帧结构光主题，内容经研究者过目）+ `knowledge/collision-bank.json` + validate schema 校验（严格拒未知键）。
- 验收：pytest 全绿 · `validate --strict` 全绿 · 制造重复行后 validate 能报出（反向测试）。

**W1 检索广度**
- 1.1 `sources.py` 拆分 + 注册表；`test_architecture` LAYER 增 sources=2，横向例外扩为 runs+sources（附"信息方向"专测：sources 不得 import 任何 L2）。
- 1.2 新适配器 DOAJ / DBLP / OpenReview（各：离线解析测试 + smoke 真记录测试；DBLP ≤1req/s+429 退避；OpenReview 按 `content.title` 过滤笔记）。
- 1.3 `channel_health` 三态 + 摘要 600 截断 + 并发扇出（canon `search.max_concurrency=4`）。
- 1.4 `search --expand`（OpenAlex 前/后向引文）。
- 1.5 canon：`search.active` +doaj、`search.available` [dblp, openreview]（每条带 why = 实测证据）。
- 验收：离线全绿 + 5 ACTIVE 与 2 按需源各一条真记录（smoke）· search P95 实测记录。

**W2 深读质量**
- 2.1 pdf 完整性门（canon `pdf.min_bytes=100000`）。
- 2.2 `pdf-extract --run/--paper-key/--render`（页文本缓存 + 页 PNG）。
- 2.3 claims 页作用域硬 lint（±1 页容差；正反例测试）。
- 2.4 `pdf-fetch`（Unpaywall→arXiv→EuropePMC；smoke：真抓 ≥1 篇 OA）。
- 验收：合成 PDF 全链绿；真 OA 抓取 ≥1；假 quote 被拒。

**W3 Zotero 深度**
- 3.1 主题标签 + canon `zotero.tag_prefix`。
- 3.2 `zotero-notes`（仅 CONFIRMED；写 library + 镜像 SHA 一致；幂等重生成）。
- 3.3 README 插件互补矩阵入库。
- 验收：note.md 生成+镜像测试；一次真实导入由研究者确认（列入 W6 清单）。

**W4 idea 质量**
- 4.1 novelty 三态契约与校验 · 4.2 失败账本硬拦 · 4.3 碰撞库接入 idea-brief · 4.4 disproof + publish 五件渲染 · 4.5 质量卡盲评任务书。
- 验收：正反例测试；用它给"现存失败账本 slug"做命中测试；disproof.md 完整渲染。

**W5 自动化与接口**
- 5.1 批量模式 ×2 · 5.2 `run-start --topic` / `query-brief --topic` / `session-brief` 主题行 · 5.3 README（23 命令表 + 互补矩阵 + 主题扩展示例）+ test_docs + FOUNDATION-DESIGN 同步（文件树/模块表/契约摘要/命令数）。
- 验收：README↔parser 一致性绿；`query-brief --topic` 含 transfer 族输出样例。

**W6 收口**
- 6.1 全量 pytest + ruff + `validate --strict` + `backup-verify`；分支合并 master（合并前 CI 绿；结构性改动走分支 = 红线 H3/E3）。
- 6.2 **二轮 e2e**（用 topics.json **新加的第二主题**证明扩展接口）：触发 → query-brief --topic → search（含 transfer 显式投放 dblp/openreview）→ screen-rank → paper-add --batch --pdf → pdf-fetch / pdf-extract --run → claims-add --batch（页 lint）→ claims-view → zotero-manifest/write/readback + zotero-notes → idea-brief --topic → idea-add → publish（五件）→ 研究者 verdict 回填 → run-finish。
- 验收：session-log 恰 1 行新遗骸 · 重复行零 · 交付目录 ≥5 件 · coverage=1.0 维持。

---

## 8. 预算账（红线：代码 ≤4000 / 测试 ≤3000 / canon ≤200 / 模块 ≤300）

| 项 | 现值 | 目标 | 说明 |
|---|---|---|---|
| 代码 | 2582 | ≈3400 | +sources.py(~275)；search/pdf/zotero/idea/report/validate/cli 增量；contracts 与 cli 贴身，靠压缩注释守住 300 |
| 测试 | 1807 | ≈2300 | 每门禁配正反例；smoke 独立标记 |
| canon | 119 | ≤165 | 新增 8 条（active/available/min_bytes/avoidance/tag_prefix/topics.file/collision_bank.file/max_concurrency），每条 why |
| 模块 | 14 | 15 | +sources.py（L2）；search.py 拆分后 ≈220 |
| 命令 | 21 | 23 | +pdf-fetch、+zotero-notes |
| docs | 7 件 | 7 件 | 本文件原地升版；不新增报告文件 |

---

## 9. 明确不做 + 风险

**不做**：PubMed/Lens（研究者裁决）· Google Scholar/Scopus/WoS 抓取 · Sci-Hub · S2/OpenCitations/OSF/HAL/OpenAIRE/bioRxiv-API（覆盖重叠或过慢，本节记录即止）· 表格/公式自动抽取承诺 · RAG/向量/embedding（dormant）· cron/无人值守（研究者裁决）· 冻结/归档/侧账/隔离（哲学）· 新 agent 框架 · 第二解析器（docling/MinerU 实装）。

**风险与对策**：DBLP 突发 429 → ≤1req/s + 退避重试，两次失败即信封降级 · 源增多导致 P95 上升 → 并发扇出 + `--backend` 定向 + 实测记录 · OpenReview 笔记类型混杂 → 按 title 过滤 + smoke 校准 · W6 二轮 e2e 若话题文献量不足 → 换用已有主题重跑（接口验证不受影响）· 预算触碰 → 各文件留 ≥10 行余量，优先级：R3/R5 > R4 > R2/R1 增量。

---

## 10. V1 资产对照（本次审计处置摘要，全量见审计报告）

- **absorb（已并入本版设计）**：PDF 完整性门 · 三态通道语义 · 600 字截断 · novelty provenance/confidence 与"零命中≠新颖" · 页作用域 lint · 失败账本双阈值 avoidance · 碰撞领域库（简化内嵌）· disproof schema（去可执行化）· reviewer 证据绑定评分（会话版）· "派生视图/唯一机器知识层"纪律（已有）。
- **adapt**：引文两跳 → OpenAlex expand 40 行 · Zotero 冻结脚本+RESULT_PREFIX → 已由 manifest/readback 体系替代（pyzotero 直写，弃 pywinauto）· 反馈 4 路回写 → 单账本+派生（已有）。
- **discard（确认不带，审计再证）**：QUERY_MATRIX/领域硬编码（13 处，W37 全查询污染实证）· score_ideas 词袋 Jaccard · rubric loop/dag_score/prune_branches · eval_harness · auto-draft 模板插值 · state.json/permissions/契约 shim · 一次性回溯账本 · figure_pipeline/knowledge_graph/evidence_index/vector · pdf-manual-queue · Tavily/校网通道/3 MCP · 硬编码盘符。

---

*执行：W0→W6 顺序推进，每波次收口跑 pytest+ruff+validate --strict 并 commit（分支 `v2.1`，W6 合并）；执行期内不新增范围。本文件即执行蓝图；代码落地时同步 FOUNDATION-DESIGN/README。*
