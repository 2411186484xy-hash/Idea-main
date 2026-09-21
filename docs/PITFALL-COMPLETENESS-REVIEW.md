# 避坑清单完备性审查（Step 1 · 2026-09-21）

> 审查对象：`docs/FINAL-REPORT.md`（V1 弯路审计，24 条弯路 + 52 条红线）
> 审查方法：对照 V2 全部现行代码（11 个 pipeline 模块 + 5 个测试 + canon/permissions/pyproject）逐条复核，再独立扫描 V1 功能面。
> 结论：**报告主体可靠性极高（10/10 复发属实、6/6 未覆盖属实），但存在 1 处误判、13 处漏检、8 类结构性缺口**。本文件是其增补件，红线总数 52 → 60。

---

## 1. 报告声明复核结果

| 报告声明 | 复核结果 |
|---|---|
| 5 处策略数值双写（runs.py:21 / idea.py:15,26,117 / papers.py:10） | ✅ 属实，且 canon 内均有同名定义 |
| 路由枚举矛盾（`counter_boundary` vs `counter`/`boundary`；缺 `frontier`） | ✅ 属实，canon 无 `coverage.routes` 键 |
| 无 `.git` | ✅ 属实（`Test-Path .git` = False） |
| 悬挂 active run `WEEKLYRUN-20260920-120000` | ✅ 属实 |
| `conftest.py` 仅 4 行、无污染守卫 | ✅ 属实，隔离靠逐测试手工 monkeypatch |
| canon 搬回 V1 已证伪机制（week_modes 2:2 / parallel 6-5-4-4-5 / l2_quota hard / v3 模板） | ✅ 属实（canon:60-61 及 30/32/58 行） |
| `common.py:22-25` 绝对路径 + identity 不同步 | ✅ 属实，`check_identity_sync()` 只查 Zotero 两项 |
| `allow_with_recent_backup` 假严格 | ✅ 属实（permissions.py:37-38 直接放行） |
| 死代码 runs.py:267-268 / validate.py:68-69；`papers.py` 无 CLI；双版本 `__pycache__`（cpython-310 + 314） | ✅ 全部属实 |
| vector extra 休眠 / claims 双写模式 / REFERENCED_ACTIONS 手工维护 | ✅ 属实 |

**误判 1 处**：报告 §6.1 把"核心依赖最小化（3 个）"列为已正确吸收——实测 `arxiv`/`pyalex`/`pyzotero` **全部零 import**（`net.py` 用 stdlib 自实现 OpenAlex/arXiv）。这不是"最小化"，是"声明了从未落地的依赖"（A5 同型问题）。处置：核心改 **stdlib-only 零依赖**，pyzotero 等到 Zotero 实装阶段再作为 extra 引入。

## 2. 报告漏检的新问题（13 条，含 2 个 P0 级 bug）

| # | 问题 | 位置 | 严重度 | 修复方案 |
|---|---|---|---|---|
| N1 | **冻结哈希含 `updated_at`，机制自失效**：`_freeze`/`verify_freeze` 的 payload 只排除 `frozen_hashes`，而 `_write_run` 每次都改 `updated_at`。`finish()` 两次写盘跨秒 → verify 立即漂移；`refreeze()` 改动未落盘就取哈希 → verify 必然漂移。现有测试因两次写盘恰好同秒而假绿 | runs.py:206-228, 244, 260-261 | 🔴 P0 | 冻结 payload 排除 volatile 键 `(updated_at, frozen_hashes)`；`finish`/`refreeze` 改为内存中一次算哈希、单次写盘；测试用 mock 时钟覆盖跨秒场景 |
| N2 | **reconcile 吞数据**：被跳过的 side-ledger 条目随 `write_text("")` 一并清空，冲突条目无迹可寻 | runs.py:162 | 🔴 P0 | skipped 条目移入 `mechanized-prescreen.skipped.jsonl`，侧账只删除已晋升行 |
| N3 | **OpenAlex 摘要恒为空**：API 返回 `abstract_inverted_index` 而非 `abstract`，`normalize_openalex` 取空 → L2 卡 one_line_evidence 为空。V1 参考实现在 `literature_search_tools.py:1067-1074` | net.py:91 / literature.py:26 | 🔴 P0 | 按倒排索引位置重排还原摘要（≤600 字截断） |
| N4 | **docstring 声明 "24h-stale warning" 无任何实现**——A5（声明超前于实现）在 V2 内已复发 | runs.py:5 | 🟠 P1 | 在 `validate` 实装：active 且 `paper_candidates==0` 且 `updated_at` > 24h → error |
| N5 | **`write_json`/`_append_jsonl` 非原子写**：崩溃时状态文件半写损坏（报告 B5 只治了锁，没治 crash-safety） | common.py:53-57 / runs.py:137-141 | 🟠 P1 | tmp 文件 + `os.replace`（同盘原子） |
| N6 | **canon 声明 Crossref 撤稿通道，但无 Crossref 客户端**——retraction 双通道中一条是空头支票（A5 又一例） | canon:26 vs net.py | 🟠 P1 | Phase 2a 补 Crossref 客户端（update-to type=retraction 查询）或先从 canon 移除该声明 |
| N7 | **反馈/claims 写入无 `parent.mkdir`**：`knowledge/` 缺失时 `record_feedback`/`append_claim` 直接崩 | idea.py:76 / claims.py:18 | 🟠 P1 | 写前 mkdir（`write_json` 已做，裸 open 补齐） |
| N8 | **`contradiction_matrix` 按 `topic` 分组，但 `topic` 不在 `REQUIRED_FIELDS`** → 全部落 "general"（B3"字段建了就要流转"实例） | claims.py:38,11 | 🟠 P1 | `topic` 入必填字段或分组键改 `paper_key` |
| N9 | **`jcr_soft_gate` 的 registry 无任何来源**，函数永远 watchlist（B3 又一例） | literature.py:63-73 | 🟠 P1 | 挂 `knowledge/jcr-registry.json`（机器只读、人工核验才写入），或删函数到实装时再加 |
| N10 | `runs.start` 的 `empties` 计数的是**全部 active** 而非"空" run，名不副实 | runs.py:48-54 | 🟡 P2 | 只数 `paper_candidates==0` 的 active |
| N11 | `permissions._policy` 的 `lru_cache` 无失效通道，运行期改 permissions.json 读到旧策略 | permissions.py:19-21 | 🟡 P2 | 加 `reload()`，或去掉缓存（文件 <1KB） |
| N12 | `is_retracted` 的 `any(m in update_to ...) and "retraction" in update_to` 双条件冗余（"retraction" 包含 "retract"） | literature.py:50-51 | 🟡 P2 | 单条件 + 单测锁定语义 |
| N13 | `idea.publish` 生成占位内容且无 slug 合法性校验（报告已列 M5，此处补充：`publish("C1")` 这类 V1 污染事故路径在 V2 现行代码可直接复现） | idea.py:120-134 | 🟠 P1 | slug 正则门禁 + 测试环境交付根强制重定向 |

## 3. 清单结构性缺口（8 类，红线 52 → 60）

以下维度在 24 条弯路 + 52 条红线中**没有对应规则**，但 V1 实际踩过或同类仓已证明必要：

| # | 新红线 | 依据 |
|---|---|---|
| R53 | **LLM 上下文成本纪律**：每个 CLI 输出、每份注入文档有 token 预算意识；注入物按需生成而非全量注入 | V1 benchmark 实测 skill 98 token vs MCP 13,448 token；E2"报告产出>消费能力"的上下文版 |
| R54 | **测试性能分层**：fast（<30s 全量）/ slow（网络、IO 重）/ smoke（外部服务）三层标记，默认只跑 fast | V1 pytest 183s 无分层，单机循环被拖慢 |
| R55 | **派生索引可重建**：一切索引/视图必须能从真源一键重建，或根本不落盘 | V1 `state.runs.idea=[]` 而 26 个 IDEARUN 在盘（角度6） |
| R56 | **工具链版本单源**：ruff/pytest 版本只允许 pin 在 pyproject 一处，CI 与 pre-commit 引用同源 | V1 ruff 本地 0.16.3 vs CI 0.15.14 偏斜 |
| R57 | **重构完成度**：结构性拆分要么完成要么回退，禁止"phase 1/3"长期滞留（半途而废的宽 API 面比大文件更糟） | V1 god-split 停在 1/3，门面残留 137 行 noqa re-export |
| R58 | **状态文件 schema 版本化**：每个状态文件带 `schema_version`，跨版本读写必须显式迁移 | V1 state.json 脏键堆积（revision 880、18 个伪周键） |
| R59 | **备份可恢复性**：备份必须抽样恢复验证，"zip 存在"≠"可恢复"；备份清单由程序生成 | V1 208MB 备份从未验证恢复路径，registry note 与磁盘不符（D2） |
| R60 | **secrets 卫生**：.env 新增键必须同 commit 有消费方；pre-commit 挂 detect-private-key；无消费方的键即删 | V1 `LENS_API_KEY`/`NCBI_API_KEY` 全仓无消费方（A5） |

## 4. 对整改路线（P0/P1/P2）的增补

在原 18 项基础上增补（原编号不变）：

- **P0 增补**：#19 冻结 volatile-keys 重构（N1，含跨秒测试）；#20 reconcile 隔离区（N2）；#21 OpenAlex 摘要还原（N3）；#22 原子写（N5）；#23 删未用依赖、核心 stdlib-only（误判修正）
- **P1 增补**：#24 实装 24h-stale 校验（N4）；#25 Crossref 通道落地或移除声明（N6）；#26 写路径 mkdir + topic 字段流转（N7/N8）；#27 JCR registry 落位或删函数（N9）；#28 slug 门禁提前到 P0 同批（N13）
- **P2 增补**：#29 empties 语义修正（N10）；#30 permissions 缓存失效（N11）；#31 测试性能三层标记（R54）；#32 state schema_version 落地（R58）

## 5. V1 功能面盘点（V2 铺开的对照基线）

V1 现役 `tools/` 55 文件约 24k 行、74 命令。按"V1 用它成功过吗"分三档：

**A 档（V1 真实产出过价值，V2 必须重写到位）**：run 状态机（13 收口 run）、多源检索 + 撤稿双通道（3 现役通道）、mechanized 侧账、L2 卡、页锚 lint + writer-verifier、claims 中枢（204 条）、Zotero manifest+回读（4 集合治理）、idea pool + 6维卡 + 失败账本（7 条真实拦截）、交付分层（30 个交付目录）、idea-feedback CLI（机制在、使用为零）。

**B 档（V1 建了但未闭环，V2 先建闭环再谈扩展）**：反馈回路（29/29 verdict 缺失 → V2 第一屏数字）、living-queries 精度退役、查新多查询、碰撞（open-collider 借鉴）、feasibility_profile / gap-map（现为占位）。

**C 档（V1 已证伪/负资产，V2 不带过来）**：week_modes 轮换、parallel 数值、L2 配额 hard 拒收（改 hard + partial 双通道）、depth-v3 模板族、cold_recall、skill 市场自建、无人值守 cron、qdrant/vector、litellm 路由、Zotero 18 天绕路方案。

---

*本文件绑定的改动：`docs/V2-MASTER-PLAN.md` Phase 0/1 全部条目由本文件 §2/§4 直接派生。*
