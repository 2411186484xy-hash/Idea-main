# GitHub 同类仓库考察报告 · 核验版（2026-09-21 第二轮重审）

> 口径：**本版所有 ★/许可/最近推送均来自本轮会话内的 GitHub API 原始返回**（主对话直查 5 仓原始 JSON + 3 个深挖代理逐仓 API 核验 + 源码树实读）。第一轮约 230 仓的广度清单保留为线索（§4），但**不再作为事实依据**。
> 纪律：borrow-not-merge；AGPL/GPL/NOASSERTION/自定义许可/无 LICENSE 禁融，只做设计借鉴；停更/放缓仓不新增依赖、不作为"活跃最强"锚。
> 本文件绑定：`docs/FOUNDATION-DESIGN.md` 的"同类最强锚"栏 + canon `external` 触发表。

---

## 0. 结论（重审后修正）

1. **无完全对标仓**（维持）：没有一个开源仓同时具备 canon 单真源 + run 状态机 + 冻结哈希 + Zotero 回读审计 + writer-verifier 分离 + 反馈闭环。V1 治理层是独有资产。
2. **编排类最强锚换了人**：deer-flow 实测 82,773★ / MIT / 昨日仍在推送，是长周期研究运行时的最强参照（artifact+hash、ThreadState、run/stream/wait 边界、子代理隔离）。storm（31,455★/MIT）**已放缓约一年**（最后真实推送 2025-09-30）——多视角提问降级为"设计借鉴"，不再作为活跃标准。
3. **引用核验仍是全行业短板**（维持）：gpt-researcher 29,546★ 也只做到段级 source-tracking；页锚定 claims + 三态 verifier 仍是第一梯队差异点。
4. **第一轮的错误必须在方案里清零**（见 §1 纠正日志）——这正是"同类最强以 GitHub 实测为准"的意义。

---

## 1. 纠正日志（第一轮 → 本轮 API 实测）

| 仓 | 第一轮说法 | 本轮 API 实测 | 影响 |
|---|---|---|---|
| bytedance/deer-flow | ~22k★，许可待核实 | **82,773★，MIT，2026-09-20 推送** | 升为编排类头号锚 |
| stanford-oval/storm | ~31k★，活跃 | **31,455★，MIT，但 pushed_at=2025-09-30（放缓近一年）** | 降为设计借鉴 |
| assafelovic/gpt-researcher | ~29k | **29,546★，Apache-2.0，2026-08-27** | 维持活跃锚 |
| datalab-to/marker | **GPL-3.0 红旗** | **Apache-2.0（代理实读 LICENSE 正文）** | 解除红旗；其 builders/converters/renderers 分层可借鉴 |
| cookjohn/zotero-mcp | 许可疑 | **MIT（代理实读 LICENSE）** | 写通道参照解禁 |
| patkennedy/pyzotero | BSD | 仓库已迁移 **urschrei/pyzotero，BlueOak-1.0.0，PyPI 1.13.4** | canon external 需按新坐标 pin |
| 54yyyu/zotero-mcp | ~2.6k★ | **5,098★，MIT，2026-09-15** | 读通道参照 |
| Future-House/paper-qa | 9.2k | **9,227★，Apache-2.0，2026-09-17**（主对话直查） | 维持证据链头号锚 |
| Future-House/robin | MIT | 本轮 API 返回 **Apache-2.0**（两轮不一致，以 API 为准标注双值） | 次要锚 |
| yusuke1997/HalluCiteChecker | Apache-2.0 活跃 | GitHub 搜索未返回该仓（PyPI 0.1.1 存在） | 降为"存在性未核实"，不作为锚 |

## 2. 核验锚点表（本会话 API 实测 · 按管道段）

### 2.1 检索 / 编排 / 筛选

| 仓 | ★（API） | 许可（API） | 最近推送 | 角色 |
|---|---:|---|---|---|
| bytedance/deer-flow | 82,773 | MIT | 2026-09-20 | **编排最强锚**：ThreadState、artifact+hash、run/stream/wait、子代理隔离、MemoryManager 可插拔后端 |
| assafelovic/gpt-researcher | 29,546 | Apache-2.0 | 2026-08-27 | 多源研究代理：planner/executor/publisher 分层、source-tracking、配置体系 |
| stanford-oval/storm | 31,455 | MIT | 2025-09-30（放缓） | 多视角提问→大纲先绑证据（**仅设计借鉴**） |
| asreview/asreview | 3,788 | Apache-2.0 | 2026-09-20 | **筛选最强锚**：stoppers 类族（NConsecutiveIrrelevant/NLabeled/QuantileLabeled/IsFittable）、queriers 族、entry-points 插件注册、**工程质量标杆**（ruff+pytest 矩阵 CI、pytest-random-order、internet_required marker、setuptools_scm） |
| LearningCircuit/local-deep-research | 3,500 | MIT | 活跃 | followup_context_manager（知识积累→下一轮提问）|
| letta-ai/letta | 4,800 | Apache-2.0 | 活跃 | 记忆框架（代码主体已迁 letta-code；观察名单，不引入） |
| blazickjp/arxiv-mcp-server | 3,168 | MIT | 活跃 | arXiv 通道参照 |
| lukasschwab/arxiv.py | 1,545 | MIT | 活跃 | arXiv 客户端形态参照（V2 自实现，不依赖） |
| jannisborn/paperscraper | 542 | MIT | 活跃 | 多源元数据收集思路 |
| danielnsilva/semanticscholar | 480 | MIT | 2025-09 | S2 客户端（查新第二源候选） |
| J535D165/pyalex | 413 | Apache-2.0*（两轮不一致） | 活跃 | OpenAlex 客户端形态参照 |
| sckott/habanero | 251 | BSD-2-Clause | 活跃 | Crossref 客户端形态参照（撤稿通道） |

### 2.2 证据 / 解析 / 核验

| 仓 | ★（API） | 许可 | 最近推送 | 角色 |
|---|---:|---|---|---|
| opendatalab/MinerU | 80,347 | Apache-2.0 | 2026-09-21 | **解析最强锚之一**：render contracts（markdown/html/pdf/docx/latex/epub/structured_content/content_list_v2）、model.json/middle.json 中间结构、批处理失败落合约 |
| docling-project/docling | 67,465 | MIT | 2026-09-21 | **解析最强锚之二**：DoclingDocument 无损模型、**ErrorItem/FailureCategory/ConversionStatus 错误契约**、pipeline 分层（standard/native/vlm）、ConfidenceReport |
| datalab-to/marker | 39,867 | **Apache-2.0（实读 LICENSE）** | 2026-09-21 | builders/converters/processors/renderers/schema 分层；模型许可 OpenRAIL-M 独立 |
| datalab-to/surya | 21,405 | 未核实（权重许可独立） | 活跃 | OCR/布局/阅读顺序 |
| Cinnamon/kotaemon | 25,778 | 未核实 | 活跃 | RAG UI（超范围，长尾） |
| lukas-blecher/LaTeX-OCR | 16,567 | 未核实 | 活跃 | 公式 OCR |
| breezedeus/Pix2Text | 3,249 | 未核实 | 活跃 | 公式+布局 |
| opendatalab/UniMERNet | 501 | 未核实 | 活跃 | 公式识别 |
| Future-House/paper-qa | 9,227 | Apache-2.0 | 2026-09-17 | **证据链头号锚**：Docs/Doc/DocDetails/Text/Context 类型化引用绑定、pybtex 元数据、llm_parse_json 纪律 |
| khoj-ai/openpaper | 481 | **AGPL-3.0 红旗** | 活跃 | cell-grounded 逐格提取（仅设计思想） |
| PyMuPDF | ~8k | **AGPL-3.0（库依赖可用，禁复制其代码）** | 活跃 | 文本层第一通道 |

### 2.3 idea / 查新 / Zotero / 反馈

| 仓 | ★（API） | 许可 | 最近推送 | 角色 |
|---|---:|---|---|---|
| SakanaAI/AI-Scientist | 14,595 | **NOASSERTION（自定义许可，实读）** | 2025-12-19（停更） | 查新设计源：Novelty 1-10 JSON 字段化、审稿 ensemble（reviewer_system_prompt_base/neg/pos）、3.2e 条禁止未声明机器生成论文 |
| SakanaAI/AI-Scientist-v2 | 7,191 | NOASSERTION（同上） | 2025-12-19 | agentic tree search（BFTS）；fewshot_examples 模板版本化思路 |
| retorquere/zotero-better-bibtex | 6,689 | MIT | 活跃 | 引文键导出 |
| 54yyyu/zotero-mcp | 5,098 | MIT | 2026-09-15 | **读通道锚**：检索/摘要/批注/语义搜索/导出 |
| EvoScientist/EvoScientist | 4,948 | Apache-2.0 | 2026-09-19 | AutoSkills（记忆提炼→人审）思路 |
| TideDra/zotero-arxiv-daily | 5,952 | **AGPL-3.0 红旗** | 活跃 | 每日推荐（禁融） |
| papersgpt/papersgpt-for-zotero | 2,649 | **AGPL-3.0 红旗** | 活跃 | 禁融 |
| CL-ML/open-collider | 343 | MIT | 2026-05-16 | **碰撞锚**：BrainstormOrchestrator.run_iteration = domain→idea→scoring→finalize；score_parser JSON 纪律；phases/strategies/scoring 分层 |
| cookjohn/zotero-mcp | 未核实星数 | **MIT（实读 LICENSE）** | 2026-09-09 | **写通道锚**：add/edit items/notes/tags/collections 全写面 |
| introfini/ZotSeek | 209 | MIT | 活跃 | 本地语义搜索 |
| urschrei/pyzotero | 未核实 | **BlueOak-1.0.0**（PyPI 1.13.4） | 活跃 | Python Zotero 客户端（写通道依赖，按新坐标 pin） |
| Future-House/robin | 712 | Apache-2.0（本轮 API；首轮记 MIT） | 2026-04 | 多智能体发现（次要） |
| ChicagoHAI/hypothesis-generation (HypoGeniC) | 未核实 | MIT | 2025-11 | 假设-证据回路（PyPI hypogenic） |
| Galaxy-Dawn/claude-scholar | 未核实 | MIT | 2026-08-27 | 人决策中心理念同源（Zotero Web API 模式、safe deletion） |
| （反馈回路） | — | — | — | **行业空白**：无同类仓具备 verdict 闭环，V2 独有赛道 |

## 3. 深挖获得的可迁移机制（源码实读，含真实文件/类名）

1. **deer-flow**：`backend/app/gateway/routers/runs.py` 的 `/stream`+`/wait` 双边界；`run_models.py` 的 `MAX_CONVERSATION_REFERENCES=3` 类上限常量；`memory/manager.py` MemoryManager 接口+backends 目录；`task_continuity/` 的 state/archive/tools 三分。
2. **asreview**：`models/stoppers.py` 四停止器类族（每个独立命名+参数+可测试）；`pyproject.toml` entry-points 全插件注册；`.github/workflows/ci-core.yml` Ubuntu/Windows × Py3.10/3.13 矩阵 + ruff + 数据缓存降级策略；`pytest-random-order`（随机化暴露测试间依赖）。
3. **paper-qa**：`src/paperqa/docs.py` 的 `Docs{docs: dict[DocKey, Doc|DocDetails], texts: list[Text], texts_index}`；`core.py` 的 `llm_parse_json()`——LLM 输出一律 JSON 解析并留原文。
4. **docling**：`document_converter.py` 引入 `ConversionStatus/ErrorItem/FailureCategory`；`datamodel/extraction.py` 的 `ExtractedPageData{page_no, raw_text, extracted_data, errors}`——**每页带错误清单**的输出契约。
5. **MinerU**：`mineru/render/` 九种渲染各自成文件 + `contracts.py` 统一合约；`types.py` 从 `docvortex.schema` 导入共享类型——**输出契约独立于实现**。
6. **open-collider**：`brainstorm.py` 的 `run_iteration()` 四阶段顺序编排；`scoring/score_parser.py` 解析 LLM JSON 评分——**评分解析与生成分离**。
7. **AI-Scientist**：`generate_ideas.py` 要求 JSON 含 `Novelty: 1-10`；`perform_review.py` 的 `get_batch_responses_from_llm` + 三套 reviewer 系统提示（base/neg/pos）——**多视角评审 ensemble 的最小形态**。

## 4. 长尾线索（第一轮广度，**未复核，仅作线索不作依据**）

综述生成：AutoSurvey / SurveyX（license unknown，禁融）/ SurveyForge / LitLLM(Apache-2.0) / MiniCPM4-Survey / ARISE / SurveyG。评审模拟：AgentReview（CC BY-SA 4.0）/ marg-reviewer / OpenReviewer / TADDLE。引文核验新兴：draft-detective / CiteGuard / Valsci / CiteTracer（均为小仓或未核实存在性）。MCP 学术服务器：openalex-mcp / pubmed-mcp / scholar-mcp 等约 14 仓。arXiv 推送：arXivDigest 等。假设生成：GT4SD / LLM-SCI-GEN / InternAgent(NovelSeek 后继，未核实)。停更/存档：open_deep_research（已存档）/ dzhng 放缓 / nougat / litstudy / arxiv-sanity 系。

## 5. 许可红旗终表（禁融清单）

- **AGPL-3.0**：PyMuPDF（作为库依赖在内部工具使用可以，禁复制代码）、openpaper、papersgpt-for-zotero、TideDra/zotero-arxiv-daily、khoj。
- **NOASSERTION/自定义**：SakanaAI/AI-Scientist v1/v2（自定义许可，含 3.2e 论文声明条款）。
- **非 OSI**：LiteResearcher（CC BY 4.0）、AgentReview（CC BY-SA 4.0）。
- **license unknown**：SurveyX。
- **解禁**（本轮实读 LICENSE 纠正）：marker（Apache-2.0）、cookjohn/zotero-mcp（MIT）。

---

*本核验版的数字快照日期：2026-09-21。执行期若 canon external 表引用某仓，以引用当日 API 复核为准。*
