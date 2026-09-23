# V2 底层设计 v2.1（2026-09-23）

> 哲学（定调）：**一开始就做对，所以以后没必要改——不是加锁不许改。数据吸收完就删，不冻结、不归档、文件不堆积。**
> V1 的有效资产全部继承（§1.2，15 项）；V1 与 v1.1 方案里的机制脂肪一律不带（§1.1，10 类删除）。
> 定位：研究者主权的单机科研辅助工具。认知判断归会话内模型；本地代码只做**通道、门禁、审计、状态**。止于 idea 交付。性能底线 = V1 实测（§10）；功能标准 = GitHub 同类最强（核验锚，见 `docs/GITHUB-SURVEY-2026-09-21.md`）。

---

## 0. 三条根原则（代替 v1.1 的"冻结表"）

1. **做对一次**：底层 = 契约（contracts.py 数据模型）+ 纪律（store.py 全仓唯一写入口）+ 端口（search/pdf/zotero 隔离易变外部）。靠分层与测试保持形状，不靠冻结机制。
2. **吸收即删（数据生命周期）**：run 是临时工作状态。收口（完成或放弃）→ 产物早已实时写入知识层/交付区 → **run 文件删除**。磁盘上只留"现在还活着的"：claims 知识、在途 idea、教训、反馈、session-log 一行。**git 是仓库的备份；D:\Research\Backup 是交付物的备份；知识层是唯一的机器记忆。** 没有冻结件、没有隔离区、没有归档目录。
3. **少即是稳**：每加一个机制先问"V1 验证过它的价值吗？没有 → 不加"。命令 21 个、模块 13+1 个、canon ≤200 行、pipelines+cli ≤4k 行。

### 0.1 文件架构（三区 · 含生命周期标注）

```
区1 仓（代码治理区）d:\AppData\Project\Idea
  cli.py                    23 命令，stdout UTF-8
  pyproject.toml            核心 stdlib-only；extras: pdf→pymupdf, zotero→pyzotero
  pipelines/                15 模块（≤300 行/个）
    contracts  store  canon  net  search  sources  pdf  papers  claims  idea
    feedback  zotero  runs  report  validate
  governance/  workflow_authority.json   canon（数值+why，≤200 行；文件名遵 AGENTS.md）
  knowledge/   [持久·git 跟踪·文本可 diff]
    corpus-claims.jsonl(追加)  idea-pool.json(仅在途)  feedback.jsonl(追加)
    failure-ledger.jsonl(追加)  session-log.jsonl(一行/run)  jcr-registry.json
    topics.json(主题包·加主题=加数据)  collision-bank.json(碰撞源域库)
    .cache/(工作缓存·git 排除：抽取页文本/页 PNG)
  runs/        [临时·git 排除·收口即删] 当前活跃 run 的工作状态
  docs/        README(命令表)  ENVIRONMENT  GITHUB-SURVEY  FINAL-REPORT
               PITFALL-REVIEW  FOUNDATION-DESIGN  MASTER-PLAN（共 7 件，不增）
  tests/       conftest + 每模块测试 + test_architecture + test_docs
  .gitattributes(LF)  .pre-commit-config.yaml  .github/workflows/ci.yml

区2 交付区（D:\Research · 只写交付物，永不写状态/账本）
  D:\Research\Paper   _inbox\(研究者投入的新 PDF) → library\<paper_key>\（paper-add 归档）
  D:\Research\Idea    \<slug>\（publish 5 件套 + researcher-decision.json；V1 已有 29 目录）
  下游两仓只读 D:\Research\Idea，永不回写。

区3 备份区（D:\Research\Backup · 镜像，V1 已在用）
  D:\Research\Backup\Paper ← D:\Research\Paper（paper-add 归档即镜像）
  D:\Research\Backup\Idea  ← D:\Research\Idea（publish 即镜像）
  backup-verify：新鲜度检查 + 全件 SHA 恢复验证。

禁入（canon forbidden_input_roots）：E:\Project、trae-input、C:\Users\24111\Documents\3D重建科研。
```

路径纪律：四个数据根只读 canon identity，代码零硬编码；测试中 knowledge/runs/数据根全部经 `IDEAOS_*` 环境变量重定向（conftest session 级），真实数据根与真实账本零写入。

---

## 1. 融合决策总表

### 1.1 机制脂肪 → 真删（V1 的病 + v1.1 方案自己的病）

| 机制 | 处置 | 为什么敢删 |
|---|---|---|
| 冻结哈希 / refreeze / VOLATILE 键 | **全删** | run 是临时状态，吸收即删，没有"被篡改的历史"需要保护；崩溃安全由原子写负责；N1 类 bug 连同机制一起消失 |
| 预筛侧账 + reconcile 晋升 + 隔离区 | **全删** | 预筛结果直接进 run.paper_candidates（带 screen_status 字段），单一真源；无同步环节即无 N2 吞数据 |
| decisions.jsonl 决策账 | 删 | git 历史 + canon 每条 why 字段足够；V1 实证 62.3KB 纯肥胖 |
| anti-pattern-cards.json 独立文件 | 删 | failure-ledger 加 lesson 字段；idea-brief 渲染时注入最近教训（派生视图不落盘） |
| gates 注册表 + 触发率计数 | 删 | 门禁 = 领域模块里的纯函数 + 故意触发测试；validate 直接调用，无需注册表 |
| permissions.py / permissions.json | 删 | 备份新鲜度 = canon 一个数值 + backup-verify 一个命令 |
| migrate 迁移命令 | 删 | YAGNI；加载器拒绝未知 schema_version；真要迁移时数据层是小 jsonl，一次性脚本 + git 留痕 |
| run-status / search-log / delivery-check 命令 | 并入 | session-brief 显活跃 run；query-brief 显查询历史；publish 内置交付校验 |
| contracts 字段冻结测试 | 删 | 正常单测 + schema_version 足够；"只增不改"是意愿不是锁 |
| run.artifacts[] 登记表 | 删 | 产物各有真源：claims→账本、PDF→canon paper_root、交付→canon delivery_root；run 不需要再记一份 |

### 1.2 V1 有效资产 → 继承（15 项，用户定调：V1 不是一无是处）

| V1 资产（实证） | V2 继承方式 |
|---|---|
| run 状态机 + partial 诚实收口（11 run：10 partial + 1 completed，零悬挂） | 状态机保留；partial = 可续跑（--resume）；新增 --absorb 放弃收口 |
| writer-verifier 盲分离 | verifier 只看文本 dump + notes，出三态 verdict；CONFIRMED 条目抽查 quote 逐字命中 |
| 页锚定 claims（V1 招牌） | 硬门：缺 page_anchor / quote 被 lint 拒绝 |
| OpenAlex inverted-index 摘要还原（V1 literature_search_tools.py:1067 正确实现） | 直接移植；V2 骨架的恒空 bug（N3）随重写消失 |
| 覆盖四路由 direct/counter_boundary/transfer/frontier | 候选 discovery_class + run.coverage，V1 语义原样 |
| corpus gate 3+1+1 | idea-add 硬门（evidence_refs 校验） |
| 6 维质量卡 + 6 攻击清单 | canon 维度（novelty/rigor/feasibility/clarity/data_availability/venue_fit）+ hold 规则 |
| Zotero 三段式 manifest+SHA+回读 | 原样保留（行业空白：无同类 MCP 仓有回读审计） |
| 失败账本 → 下次生成前强制注入 | failure-ledger.jsonl + lesson 字段；idea-brief 注入、idea-add 校验已读 |
| 交付 4 件套（DEC-0032/0035 分层） | publish 真实模板 + 内置校验 + 镜像 canon idea_mirror_root |
| 反馈回路机制 | **第一里程碑**：feedback-import-v1 先回填 29 存量，coverage>0 前不扩供给 |
| 网络纪律（OpenAlex polite pool、arXiv 3s 间隔、UA） | search.py 常量 + canon |
| SSL certifi 兜底 / 代理清空（沙箱实测） | search.py 内置 + ENVIRONMENT.md 记事实 |
| 追加式 jsonl 账本形态 | claims / feedback / failure-ledger / session-log 全部 jsonl |
| 查询日志（query_log 入 run） | 保留；query-brief 用它做去重（local-deep-research followup 思路） |

### 1.3 GitHub 最强锚 → 借鉴（borrow-not-merge；锚点数字见 GITHUB-SURVEY 核验版）

| 锚 | 借什么 | 落点 |
|---|---|---|
| deer-flow 82,773★ MIT | run 生命周期边界（run/stream/wait 分离的纪律） | runs.py 状态机边界 |
| paper-qa 9,227★ Apache-2.0 | 类型化引用绑定；LLM 回流"原始+解析"双存 | Claim 契约；claims-add/idea-add 回流 |
| docling 67,465★ MIT | ErrorItem/FailureCategory 错误契约 | ErrorEnvelope（全适配器统一） |
| MinerU 80,347★ Apache-2.0 | 输出合约独立于实现 | pdf.py 输出契约；MinerU 只是第二通道 |
| asreview 3,788★ Apache-2.0 | 停止准则（连续 N 低相关）；pytest-random-order | papers.py screen-rank |
| gpt-researcher 29,546★ Apache-2.0 | source-tracking | 段级引用必溯源证据卡 |
| storm 31,455★ MIT（放缓） | 多视角提问 | query-brief（仅设计借鉴） |
| open-collider 343★ MIT | 碰撞编排 + 评分解析分离 | idea-brief 碰撞三要素 |
| AI-Scientist 14,595★（禁融） | novelty 字段化 + 多 reviewer | 6 维卡 + verifier 多视角 |
| 54yyyu 5,098★ / cookjohn MIT | Zotero 读写面划分 | ZoteroPort 读宽写窄 |
| marker 39,867★ Apache-2.0 | 通道分层 | pdf.py channel/convert/render |

### 1.4 明确不做

V1 已证伪：week_modes、parallel 数值、L2 hard 单通道、模板族、cold_recall、skill 市场、无人值守 cron、qdrant/vector、litellm。v2.0 追加不做：**一切冻结/归档/隔离/决策账/注册表机制**。范围外：实验/论文写作/代码执行（下游两仓）。框架类（letta/langgraph/crewAI）不引入——宿主即编排器。

---

## 2. 分层与依赖（机器强制）

```
L0 contracts.py   零依赖零 IO：全部记录类型 + ErrorEnvelope + trace 事件常量
L1 store.py       唯一磁盘 IO：原子写(tmp+os.replace)/追加(fsync)/读回（时钟可注入）
L1 canon.py       canon 读取 + check_identity_sync（四根 + 常量 + data_path 数据文件锚）
L2 net.py         传输缝：直连 + SSL 证书兜底 + ErrorEnvelope（HTTP/解析错误不 raise）
L2 sources.py     源适配器（openalex/arxiv/crossref/europepmc/doaj + 按需 openreview）
L2 search.py      通道扇出/去重/摘要 600 截断/引文扩展（ACTIVE 由 canon 驱动）
L2 pdf.py         PdfPort：完整性门 → PyMuPDF 文本层（缓存/页渲染）+ OA 瀑布抓取
L2 papers.py      候选管理 + screen-rank 排序/停止准则 + 标识符/撤稿门禁（含批量）
L2 claims.py      claims 追加账本 + 页作用域 quote lint + claims-view 渲染（含批量）
L2 idea.py        idea-add 校验 + failure-ledger avoidance + publish 五件
L2 feedback.py    feedback 账本 + coverage + V1 存量导入
L2 zotero.py      manifest + 写面 + 回读 + CONFIRMED 证据笔记 note.md
L2 runs.py        状态机 + absorb→delete + session-log（领域模块唯一横向依赖）
L3 report.py      session-brief / query-brief / deepread-brief / idea-brief（纯读）
L3 validate.py    结构校验（纯读：canon 同步/悬挂 run/账本完整性/主题与碰撞库 schema）
L4 cli.py         纯 argparse，stdout UTF-8
```

规则：只准向下导入；contracts 零项目依赖；唯一横向例外 = L2 领域模块 → runs.py；M3 白名单边（search→sources、sources→net、pdf→net、papers→pdf、zotero→claims）逐条在 `tests/test_architecture.py` 注明理由。任何模块不得导入 cli。`tests/test_architecture.py` 用 ast 强制依赖方向 + grep 禁裸写 + 行数预算（pipelines+cli ≤4k，tests ≤3k）。

---

## 3. 数据契约（contracts.py）

全部 dataclass、构造即校验必填、带 schema_version、可 json 化。加载器只认当前版本，未知主版本报清晰错误。**schema 纪律：改字段 = 改代码 + 一次性修数据脚本（git 留痕），不建迁移机器。**

```python
Run（临时）: schema_version, run_id, kind(weekly|idea), status(active|partial|completed),
  attempt, created_at, updated_at, completed_at?, gap_note?, topic?(主题包 id),
  paper_candidates[], coverage{direct,counter_boundary,transfer,frontier},
  idea_seeds[], query_log[{query,backend,at}], trace[{at,event,detail}], uncertainty_disclosure[]
  # trace 事件常量：RUN_START/RUN_RESUME/PAPER_ADD/SCREEN/SEARCH/RETRACT_HIT/
  #   PDF_EXTRACT/PDF_FETCH/CLAIM_ADD/IDEA_ADD/PUBLISH/ZOTERO_WRITE/ZOTERO_READBACK/FEEDBACK

PaperCandidate: schema_version, title, paper_key(doi:>arxiv:>pmid:>openreview:>sha12: 前缀规范),
  identifiers{doi?|pmid?|arxiv_id?|openreview_id?|pdf_sha256?}(≥1), year?, venue?, cited_by_count?,
  discovery_class(四路由), source_backend, sources[{channel,query,at}] 来源轨迹,
  abstract, abstract_sha256,
  retraction{status(none|flagged|confirmed), checked_backends[], checked_at},
  screen_status?(pending|ranked|selected|rejected),
  evidence?{one_line_evidence, evidence_role}   # L2 卡折叠为字段

Claim: schema_version, id(CLM-YYYYMMDD-NNN), paper_key, topic(必填), text,
  quote(必填·逐字·页作用域 lint 对抽取缓存 ±1 页核验), page_anchor(必填),
  confidence(high|medium|low),
  verifier_verdict(CONFIRMED|DEVIATED|NOT_FOUND), verifier_note?, created_at

IdeaCandidate: schema_version, slug(^[a-z0-9][a-z0-9-]{2,}$), title, hypothesis,
  collision{seed, source_domain, target_domain},
  disproof{experiment, controls, decision_rule, failure_interpretation}(必填·纯设计),
  screening_note?(全 empty 查新时的降级记录),
  quality_card{novelty,rigor,feasibility,clarity,data_availability,venue_fit}(1-5+rationale),
  attacks[6], novelty_log[{query,backend,result(hit|empty|error),confidence(strong|weak),top_match?,note}],
  evidence_refs[](corpus gate 3+1+1), status(draft|published|accepted|rejected|uncertain)

Feedback: schema_version, slug, verdict(accept|reject|uncertain), reason(必填), at
FailureEntry: schema_version, slug, stage, reason, lesson?(下次生成前注入的一句对策), at
ZoteroManifest / ReadbackReport / ErrorEnvelope: 同 v1.1 定义
```

---

## 4. run 生命周期（核心简化）

```
active --run-finish-->            completed：校验 → 打印摘要 → session-log 追加一行 → 删 run 文件
active --run-finish --partial "gap-note"--> partial（可 --resume 续跑，attempt+1）
partial --run-finish --absorb "gap-note"--> 同 completed 路径（放弃收口，诚实留 gap）
```

- **幂等**：paper-add 重复 paper_key 拒绝；claims-add 重复 id 拒绝；finish 对终态拒绝。
- **24h-stale**：active 且 candidates 空 且 updated_at>24h → validate 警告（提示吸收或删除）。
- **单进程假设**：单机单操作者串行；原子写只防崩溃半文件，不做锁。
- **吸收安全**：finish 前校验账本计数与 run 内计数一致才删；session-log 一行记录 {at, run_id, kind, papers, claims, ideas, gap_note?}——这是 run 的唯一遗骸。

**idea 生命周期**：draft →(publish)→ published（交付区为真源，**pool 除名**）→ verdict 回填 feedback.jsonl；rejected → failure-ledger 记 lesson。**idea-pool.json 永远只含在途工作。**

**单写者所有权**（validate 自检）：runs/ → runs.py；corpus-claims → claims.py；idea-pool → idea.py；feedback → feedback.py；failure-ledger → feedback.py（reject 回填）/ idea.py（读取）；zotero 件 → zotero.py；canon paper_root 归档+镜像 → paper-add；library note.md → zotero-notes；canon delivery_root 交付+镜像 → publish；canon → 人工。

---

## 5. 端口（易变隔离）

- **SearchPort**：`search(backend, query) → list[PaperCandidate] + ErrorEnvelope?`。ACTIVE 五通道（openalex+arxiv+crossref+europepmc+doaj，canon 驱动）+ 按需源（openreview）；并发扇出 + 摘要 600 截断 + `--cited-by/--references` 引文扩展。断网返回信封不 raise。
- **PdfPort**：`extract(path) → {text_md, pages[{page_no, raw_text, errors}], fallback_chain[], errors[]}` + 完整性门（%PDF/%%EOF/≥pdf.min_bytes）→ 抽取缓存与页渲染（claims 页作用域 lint 的输入）+ `pdf-fetch` OA 瀑布（Unpaywall→arXiv→EuropePMC）。MinerU 探针通过才启用（冷启动 ≥120s 记 ENVIRONMENT.md）。
- **ZoteroPort**：读面宽（搜索/导出/BibTeX）+ 写面窄（仅 manifest 批准条目 + `idea-os:*` 受控标签）+ 回读归档 readback-{sha12}.json；证据笔记走 note.md（library+镜像、Better Notes 手动导入，半自动边界）。

## 6. 门禁（函数，非注册表）

identifier / retraction（一票否决）→ papers.py 入 run 时；PDF 完整性门 → pdf.py（抽取/抓取/归档三入口）；page_anchor + quote 逐字 + 页作用域 → claims.py lint；novelty 三态 + 全 empty 降级记录 + failure-ledger 双阈值 avoidance + corpus_311 + slug → idea.py；stale → validate。每个都有"故意触发"测试。

## 7. 认知边界（提示包协议）

认知在会话内。CLI 只产结构化任务包（report.py，带 token 预算）：session-brief（coverage 首屏 + 活跃 run + 主题行 + 待办）、query-brief（多视角 + 主题 transfer 族 + 查询去重）、deepread-brief（writer/verifier 双书，verifier 盲）、idea-brief（碰撞三要素/库抽样 + 教训注入 + 6 攻击 + 查新计划 + disproof 设计件 + 质量卡盲评书）。回流一律 schema 校验 + 原始/解析双存（批量模式 `paper-add --batch` / `claims-add --batch` 一次供 N 条）。CLI 状态消息英文，brief 正文中文。

## 8. CLI 23 命令（README 命令表即契约，tests/test_docs 校验一致）

```
run-start(--resume/--topic)  run-finish(--partial/--absorb)  session-brief  validate(--strict)
search(--backend/--expand/--cited-by/--references)  query-brief(--topic)  screen-rank
paper-add(--pdf/--batch)  deepread-brief  pdf-extract(--run/--render/--paper-key)  pdf-fetch
claims-add(--batch)  claims-view
idea-brief(--topic)  idea-add  publish
feedback-add  feedback-import-v1
zotero-manifest  zotero-write  zotero-readback  zotero-notes  backup-verify
```

## 9. 治理（canon = governance/workflow_authority.json）

精简为：identity（四根）/ search.active / coverage / quotas / limits / external 触发表。每条 `{value, why}`——why 必须答"V1 实证 或 GitHub 哪个仓的机制"。**≤200 行，canon 不复制字段表**（字段唯一真源 = contracts.py）。AGENTS.md 在 M1 按本设计重写（侧账/冻结条款移除）——需用户过目。

## 10. 性能底线（V1 实测）

| 指标 | V1 实测 | V2 目标 |
|---|---|---|
| claims | 214 条 | ≥214，全带 quote+页锚 |
| run 收口 | 11 run 全终态 | 100% 收口且目录零残留 |
| 治理体积 | canon 73.3KB + decisions 62.3KB | canon ≤200 行，无决策账 |
| 代码规模 | ~24k 行 / 74 命令 | **≤4k 行 / 23 命令 / 15 模块** |
| 响应 | — | search P95<5s；pdf 文本层<90s/篇；fast 测试<30s |

## 11. 变更日志

### v2.0 → v2.1（2026-09-23，M3.0–M3.4；V1 审计 ×5 + GitHub 调研 ×2 + 源实测）

- **检索广度**：net/sources/search 三模块拆分；+DOAJ 进 ACTIVE（五通道）、OpenReview 按需；并发扇出（canon max_concurrency）+ 摘要 600 截断 + `channel_health`；`search --cited-by/--references`；DBLP 因 Anubis 机器人墙实测弃用。
- **深读质量**：PDF 完整性门（三入口）+ 抽取缓存/`--render` 页 PNG + claims 页作用域硬 lint（±1 页，正反例测试）+ `pdf-fetch` OA 瀑布（Unpaywall→arXiv→EuropePMC，真抓实测）。
- **Zotero 深度**：主题标签（canon tag_prefix，`idea-os:topic:<id>`）+ `zotero-notes`（仅 CONFIRMED，note.md → library+镜像 SHA）+ README 插件互补矩阵。
- **idea 质量**：novelty 三态（hit/empty/error + strong/weak，全 empty 须 screening_note 降级记录）+ V1 双阈值 failure-ledger avoidance（含 R1C2 停用词）+ 碰撞库确定性抽样接入 idea-brief + disproof 四字段必填与 publish 第五件 + 质量卡盲评书。
- **自动化与接口**：`paper-add --batch` / `claims-add --batch`；`run-start --topic` / `query-brief --topic`（transfer 族）/ session-brief 主题行；命令 21→23、模块 13→15。
- **数据层**：`knowledge/topics.json`（主题包，加主题=加数据零代码）+ `knowledge/collision-bank.json`（V1 DOMAIN_BANK 精选 18 域）+ validate schema 校验。

### v2.0（2026-09-21）

哲学修正：删 10 类防御/堆积机制（§1.1）；新增数据生命周期 absorb→delete（§4）；idea-pool 只留在途；failure 教训并入账本字段；命令 25→21；模块 15→13+1（gates/permissions/common 并入）；冻结哈希随机制消亡（N1/N2 类 bug 根除）；M0 从"骨架上打补丁"改为"端口式重写"。GitHub 锚点与 V1 资产继承不变（§1.2/§1.3）。

---

*架构与数据模型以本文为准；数值以 governance/workflow_authority.json 为准。*
