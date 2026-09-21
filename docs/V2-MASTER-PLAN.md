# V2 终极建设方案 v1.2（2026-09-21）

> 输入：`docs/FINAL-REPORT.md`（V1 弯路 24 + 红线 52）· `docs/PITFALL-COMPLETENESS-REVIEW.md`（N1-N13 + 红线 53-60）· `docs/GITHUB-SURVEY-2026-09-21.md`（核验版，API 实测）· `docs/FOUNDATION-DESIGN.md` **v2.0**（架构与数据模型以它为准——生命周期哲学：做对一次、吸收即删、少即是稳）。
> 总原则：**V1 用"再加一层机制"解决的问题，V2 删掉问题的来源；凡声明的能力当天有消费方 + 能失败的测试；每个功能段对标同类最强（GitHub 实测锚），V1 只是性能底线和坑库；V1 验证过的资产一项不丢（FOUNDATION §1.2 十五项）。**
> 量化承诺：V1 ~24k 行 / 74 命令；V2 **≤4k 行 / 21 命令 / 13+1 模块 / canon ≤200 行**，能力覆盖 V1 的 A 档功能面，质量门全部机器化。
> v1.2 变更：M0 从"骨架打补丁"改为**端口式重写**（对齐 v2.0 哲学）；删冻结/侧账/隔离/决策账/注册表全部机制项；命令 25→21。

---

## 0. "每个功能同类最强"判定表

| 管道段 | 同类最强参照（实测） | V2 打法 | 差异化护城河 |
|---|---|---|---|
| 检索发现 | gpt-researcher 29,546★；storm 多视角（放缓，仅设计借鉴） | 四通道信封（ACTIVE 驱动）+ 查询日志去重 + 撤稿双通道 | 检索门禁机器化（标识符硬门、撤稿一票否决、查询日志入 run） |
| 候选筛选 | asreview 3,788★ | 规则版排序 + 停止准则（N 读 canon）；判断归会话模型 | 候选即单一真源（无侧账同步） |
| L3 深读 | paper-qa 9,227★；MinerU/docling 解析 | PyMuPDF→MinerU 探针降级；writer-verifier 盲分离 | **页锚定 claims + quote 逐字 + 三态 verdict**（行业短板，第一梯队） |
| claims 中枢 | paper-qa 证据链（段级）；矛盾检测无核验同类锚 | 追加式 jsonl 唯一机器知识层；视图即席渲染 | 矛盾对轻量规则（同 topic verdict 相反/数值冲突） |
| Zotero | 54yyyu 读 / cookjohn 写 | 三段式 manifest+SHA→写→**回读审计** | 回读归档（同类 MCP 仓均无） |
| idea 孵化 | open-collider + AI-Scientist（禁融）+ HypoGeniC | corpus gate 3+1+1、6 维卡、6 攻击、查新多查询、碰撞三要素、教训前置注入 | **失败账本→lesson→生成前强制注入**（自进化） |
| 反馈回路 | 行业空白 | verdict+reason 必填、coverage 首屏、V1 存量 29 条先回填 | 唯一验证信号闭环，第一里程碑 |
| 治理 | 无同类（V1 独有） | canon 单真源 + 单写者 + 吸收即删 | 治理零堆积（无冻结无归档无决策账） |

## 1. 第一天不变式（12 条原版 + 8 条结构红线，见 knowledge/legacy-detectors 与 PITFALL-REVIEW）

核心继承：原子写；账本只追加；派生视图不落盘；声明即实现即测试；盘符零硬编码；工具链单源 pin；重构要么完成要么回退；schema_version 拒未知；备份抽样恢复；secrets 同 commit；上下文预算；测试真实仓零污染。

## 2. 架构 / 数据模型

**由 `docs/FOUNDATION-DESIGN.md` v2.0 全权定义**（§0.1 三区文件架构 / §2 分层依赖 / §3 数据契约 / §4 生命周期 / §8 命令面）。要点：13+1 模块；store.py 唯一写入口；run 收口即删（session-log 一行遗骸）；idea-pool 只留在途；E 盘四根环境变量化。

## 3. 执行阶段（M0→M4，每项带验收）

### M0 地基 + 端口式重写（先于一切业务铺开；每项落在**新模块**，旧骨架同 commit 删除，任何时刻无半新半旧）

| # | 条目 | 验收 |
|---|---|---|
| 0.0 | `git init` + `.gitattributes(eol=lf)` + `.gitignore` 核验（runs/ 排除、knowledge/ 跟踪）+ 首提交 | `git status --porcelain` 空 |
| 0.1 | **contracts.py + store.py + canon.py**：全部契约（构造校验、trace 事件常量）；原子写/追加 fsync/时钟可注入；canon loader + check_identity_sync（四根） | 地基三件套单测绿 |
| 0.2 | **runs.py 重写**：状态机 + absorb→delete + session-log 一行 + --partial/--resume/--absorb + 24h-stale + 幂等 | finish 后 runs/ 空且 session-log 恰增一行；终态再 finish 拒绝 |
| 0.3 | **search.py**：OpenAlex inverted-index 摘要还原（移植 V1 :1067）+ arXiv + 限流/polite pool 常量 + SSL/代理兜底 + ErrorEnvelope；断网信封不 raise | 摘要非空断言；离线单测绿 |
| 0.4 | **papers.py + claims.py**：候选管理（标识符/撤稿门禁、screen_status）+ screen-rank 排序与停止准则 + 页锚/quote lint + claims 追加账本 | 缺页锚或缺 quote 被 lint 拒；重复 paper_key/claim id 拒绝 |
| 0.5 | **cli.py + README**：21 命令接线、stdout UTF-8、README 命令表；tests/test_docs 一致性校验 | README↔parser 一致 |
| 0.6 | **test_architecture.py + conftest**：ast 依赖方向 / grep 禁裸写 / 行数预算（≤4k）+ IDEAOS_* 全量重定向 + git 污染守卫 | 故意反向 import / 裸写必红；fast 全量 <30s |
| 0.7 | **删旧骨架**（net/literature/common/gates/permissions 等旧文件同 commit 删除）；pyproject 核心 stdlib-only（arxiv/pyalex/pyzotero 移 extras）；ruff 干净 | grep 无死代码；`python cli.py validate` 零依赖可跑 |
| 0.8 | **validate --strict 冷启动全绿**（空知识层 + 空 canon 各项自检） | 退出码 0 |

### M1 治理定型

| # | 条目 | 验收 |
|---|---|---|
| 1.1 | **AGENTS.md 重写对齐 v2.0**（生命周期哲学；移除侧账/reconcile/冻结条款）——**需用户过目后提交** | 条款与 FOUNDATION v2.0 零冲突 |
| 1.2 | canon 瘦身 ≤200 行：每条 {value, why}（V1 实证或 GitHub 锚）；删未验证条目；L2 配额 hard+partial 双通道 | 每条能答出处；validate 绿 |
| 1.3 | `docs/ENVIRONMENT.md`：6 条沙箱事实（PS 吞 stdout / 代理假 502 / SSL certifi / MinerU 冷启动≥120s / GUI 寿命 / safe-delete） | README 引用 |
| 1.4 | pre-commit（ruff/eof/detect-private-key，exclude runs/）+ CI（pytest fast + ruff + 盘符扫描 + README 命令） | 故意改坏一处必红 |
| 1.5 | **feedback-import-v1**：扫 `E:\Idea\*\researcher-decision.json`（29 存量）导入；coverage 首屏化 | `feedback coverage = 29 条待回填`；coverage<阈值 idea-add 硬拦 |
| 1.6 | session-brief：coverage 首屏 + 活跃 run 状态 + 教训摘要 + 待办 | 输出四块 |
| 1.7 | claims-view 即席渲染（列表过滤 + 矛盾对），knowledge/ 无落盘视图 | 命令输出 pairs；不落盘 |
| 1.8 | docs 收口为 7 件（README/ENVIRONMENT/SURVEY/REPORT/REVIEW/FOUNDATION/PLAN），删除过程稿 | docs/ 恰 7 件 |

### M2 管道铺开（每段：实测锚 + 验收）

**2a 检索四通道**：Crossref 撤稿通道（update-to）+ EuropePMC；四通道各一条真记录；query-brief 多视角 + 去重。验收：断网信封不 raise；重复 query 标红。
**2b 筛选与归档**：screen-rank 全逻辑（撤稿一票否决、证据角色优先、停止准则 N）；`paper-add --pdf` 归档 `E:\Paper\library\<paper_key>\` + 镜像 `E:\Backup\Paper`。验收：合成 20 条排序稳定；归档后交付区/备份区 SHA 一致。
**2c L3 深读**：pdf.py 双通道降级链 + pdf-extract；deepread-brief 双书（verifier 盲）。验收：真实 PDF → 3 条带页锚 quote claims → 三态 verdict 全链绿。
**2d claims 中枢**：claims-view 矛盾对（同 topic verdict 相反/数值冲突 + severity）。验收：合成矛盾数据出 pairs；不落盘。
**2e Zotero 三段式**：manifest → 会话内 pyzotero 写（pin urschrei/pyzotero BlueOak-1.0.0）→ readback 归档 + trace。验收：模拟写入后比对通过/差异可列出。
**2f idea 孵化**：idea-brief 四合一（碰撞三要素 + 教训注入 + 6 攻击 + 查新多查询计划）；idea-add 一次收全（schema 校验 + 原始/解析双存）；corpus 3+1+1 + slug + hold 规则。验收：未读失败账本的 add 被 warn 拦。
**2g 反馈闭环（第一里程碑）**：coverage 首屏；研究者首个 verdict 回填后 coverage>0 才放新供给。验收：真实 verdict ≥1 条。
**2h 交付**：publish 生成 4 件套真实模板 + 内置交付校验（件数/slug）+ 镜像 `E:\Backup\Idea\<slug>\` + pool 除名。验收：publish 产物过校验；测试中真实 E 盘零写入。

### M3 同类最强强化

- 幻觉引文抽查：CONFIRMED 条目随机 20% 复核 quote 逐字命中。
- simulation 复盘：历史 run 重放 screen-rank 对比真实收口（asreview simulation 思想；session-log 提供数据）。
- 测试三层标记（fast<30s / slow / smoke 外部服务）；pytest-random-order。
- 性能预算实测：search P95<5s；pdf 文本层<90s/篇。

### M4 首个端到端验证 run（收官）

真实执行：触发句 → 四通道检索 → L2 10-15 → 深读 ≥1 篇全链 → claims 入账 → Zotero manifest+回读 → idea candidate（碰撞+查新+6 攻击）→ publish + 镜像 → **研究者 verdict 回填** → run-finish 吸收删除。
验收：validate --strict 绿；session-log 一行遗骸；feedback coverage>0。**此 run 成立即赢过 V1 整个治理层**（V1 41 天未闭环反馈、canon 73KB、run 永久堆积）。

## 4. 测试与质量体系

conftest（IDEAOS_* 全量重定向 + git 污染守卫）；test_architecture（方向/裸写/行数）；test_docs（README↔parser）；每模块单测 + 每个 gate 故意触发测试；ruff 单源 pin；pytest-random-order。

## 5. 风险与对策

| 风险 | 对策 |
|---|---|
| absorb 有 bug 误删数据 | finish 前账本计数校验；session-log 记计数；知识层 git 跟踪（可恢复） |
| MinerU 环境复用失败 | 2c 先落 PyMuPDF 文本层；MinerU 探针降级，不可用不阻断 |
| Zotero live API 沙箱假 502 | ENVIRONMENT.md 事实 + 代理清空内置；三段式本就半自动 |
| OpenAlex/Crossref 限流 | polite pool + mailto UA + 退避入 canon；错误信封不 raise |
| 反馈回填依赖研究者时间 | 29 存量先导入摆上台面；coverage>0 前不扩供给 |
| 范围蠕动 | scope 钉死 canon；下游两仓只读 E:\Idea |

## 6. 与 V1 功能对照

A 档 → M2 全部重写；B 档 → 先闭环再扩展（2g/2f）；C 档（week_modes/parallel/模板族/cold_recall/skill 市场/cron/vector/litellm）→ 不带。V1 冻结 runs **不迁移**（教训已在 FINAL-REPORT，数据属 V1 仓只读）。

---

*执行：第四步按 M0→M4；每个里程碑跑十角度自查（MILESTONE-REVIEW 模板并入 docs 后计 7 件内的附录）并 git 提交。AGENTS.md 重写（1.1）需用户过目。*
