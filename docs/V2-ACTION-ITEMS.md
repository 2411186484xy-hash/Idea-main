# V2 整改清单（可勾选）

> 配套文档：`docs/V1-RETROSPECTIVE.md`（完整证据与推理）
> 编号 `R*` 对应主文档 §3.2"已复发"，`M*` 对应 §3.3"尚未覆盖"

---

## P0 — 写任何业务代码之前

- [ ] **R7 建立版本控制**
  - `cd D:/AppData/Project/Idea && git init`
  - 加 `.gitattributes`（`* text=auto eol=lf`，避免 v1 的 CRLF/LF 冻结漂移）
  - 首次提交（当前 1615 行骨架）
  - 验收：`git status --porcelain` 为空、`git log --oneline` 有 1 条

- [ ] **R5 删除悬挂 active run**
  - `rm -rf runs/weekly/WEEKLYRUN-20260920-120000`
  - 在 `runs.start()` 之外增加：active 且 `paper_candidates == 0` 且 `updated_at` 超 24h → `validate` 报错
  - 验收：`python cli.py validate --strict` 通过，`status` 无 active run

- [ ] **R1 消除策略数值双写（5 处）**

  | 位置 | 现值 | 改为 |
  |---|---|---|
  | `runs.py:21` | `L2_MIN, L2_MAX = 10, 15` | `canon.get("deep_read.l2.quota_per_run")` |
  | `idea.py:26` | `need = {"direct_fulltext":3,"recent":1,"counter_or_boundary":1}` | `canon.get("idea.corpus_gate")` |
  | `idea.py:15` | `QUALITY_DIMS = (...)` | `canon.get("idea.quality_card_6d")` |
  | `papers.py:10` | `L3_PATHS = (...)` | `canon.get("deep_read.l3.paths")` |
  | `idea.py:117` | `CORE_FILES = (...)` | canon 新增 `idea.delivery_tiers.core_files: [...]`，代码从 canon 读 |

  - 验收：新增测试 `test_no_duplicated_policy_literals`——扫描 `pipelines/*.py`，断言 canon 中数值/枚举类叶子的字面量出现次数为 0

- [ ] **R2 统一路由枚举（现存 bug）**
  - canon 新增 `coverage.routes: ["direct","counter_boundary","transfer","frontier"]`
  - `runs.py:20` 与 `literature.py:14` 都从 canon 读；删除 `DISCOVERY_CLASSES`
  - 验收：`add_paper` 接受 `literature` 产出的任何 `discovery_class`；四路 finish 门禁可被正常满足

- [ ] **R4 删死代码与空目录**
  - `runs.py:267-268`（`void = ...; _ = void`）
  - `validate.py:68-69`（`if strict and warnings: pass`）
  - `delivery/`、`integrations/`（空目录）
  - `find . -name __pycache__ -exec rm -rf {} +`
  - `papers.py`：接线到 CLI（`paper-lint` / `paper-verify`）或删除
  - 验收：`ruff check pipelines tests` 干净；`grep -rn "void\|pass$" pipelines/` 无空操作

- [ ] **R6 测试隔离改造**
  - `common.py` 所有路径常量改为 `Path(os.environ.get("IDEAOS_<NAME>", default))`
  - `conftest.py` 加 session-scoped autouse fixture：把全部输出根重定向到 `tmp_path_factory`
  - `conftest.py` 加污染守卫：会话首尾 `git status --porcelain` 对比，非空即 fail
  - 验收：删除所有测试里的路径 `monkeypatch.setattr`，`pytest -q` 仍全绿；故意写一个写真实仓库的测试，守卫必须让它失败

- [ ] **M3 修"假严格"**
  - `permissions.py:37-38` 对 `allow_with_recent_backup` 直接放行，注释写"caller 负责校验"，但没有 caller
  - 二选一：(a) 真正实现备份新鲜度校验（v1 有 `common.py:274` 的 7 天模型）；(b) 把该策略降级为 `allow` 并删除误导语义
  - 验收：`permissions.check("modify_project").reason` 不再包含未实现的承诺

---

## P1 — 骨架定型

- [ ] **R3 重审 canon，逐条按"v1 成功过吗"过滤**

  | canon 段 | 现值 | 建议 |
  |---|---|---|
  | `parallel` | `retrieval:6, second_pass:5, recognition:4, deep_read:4, idea_red_team:5` | 删除数值，改为"由实测压出，见 `docs/PERF.md`"；v1 在此反复调参后 OOM（`776f37f`→`ac6c812`） |
  | `week_modes` | `2:2 per-run` + 自适应 | v1 DEC-0026/0027 同款，后被 DEC-0035 弱化；建议改为事件驱动 |
  | `runs.finish_gates.l2_quota` | `[10,15]` hard | 降为 soft + 记录缺口，或明确"L2 卡片成本低故可硬"并写理由 |
  | `deep_read.templates` | `pre_reading_questions:6` / `two_pass` / `figure_protocol_items:5` | v1 实测 47/151 应用率、`cold_recall` 零运行；建议先只保留 1 项，跑满 90 篇再谈 |
  | `claims_hub.views` | 3 个渲染视图 | 保留 1 个（claims 本体），其余按需生成不落盘 |

  - 验收：canon 每条规则都能回答"v1 用它成功过吗"，答不上的删除

- [ ] **G1.2/G1.3 常量同步断言升级**
  - `canon.check_identity_sync()` 从"只查 zotero 两项"扩展为"遍历 `common.py` 中所有 `UPPER_CASE` 常量"
  - 验收：故意改 canon 中 `identity.delivery_root`，测试必须失败

- [ ] **R8 路径收敛**
  - `common.py:22-25` 与 canon `identity` 的盘符字面量改为环境变量
  - CI 加：`grep -rnE "[A-Za-z]:[\\\\/]" pipelines/ governance/ *.py` 命中即失败
  - 验收：CI 红过一次（故意引入 `E:/tmp`）后转绿

- [ ] **M1 补 CI + pre-commit**
  - `.github/workflows/ci.yml`：`pytest -q` + `ruff check` + 盘符扫描 + 文档数值扫描
  - `.pre-commit-config.yaml`：`end-of-file-fixer` / `trailing-whitespace` / `ruff` / **`exclude: ^runs/`**
  - 验收：本地 `pre-commit run --all-files` 通过；故意改坏一处，CI 红

- [ ] **M5 交付卫生（v1 DEC-0032 三条规则）**
  - `idea.publish` 增加：slug 合法性（`^[a-z0-9][a-z0-9-]{2,}$`）、absorbed 判定、**测试环境禁用真实交付根**（依赖 R6）
  - 验收：`publish("C1")` / `publish("title-c1")` 被拒

- [ ] **R10 入口与小摩擦收敛**
  - README 首推 `python cli.py`，`os.ps1` 降为"人工便利"（v1 已验证 PS 入口在 AI 会话内 exit 0 但 stdout 为空）
  - 删除 `pyproject.toml` 的 `vector` extra（canon 声明 RAG/向量 dormant）
  - `claims.record_verdict` 改为追加式（与 `append_claim` 一致）或改为只写 verdict 事件流
  - `validate.REFERENCED_ACTIONS` 改为从代码静态扫描得出，不手工维护
  - `zotero.check_no_hardcoded_root` 改为通用：任何集合根名不得在 `common.py` 外以字面量出现
  - 验收：每条各有一个测试

- [ ] **G4.7 回收期检查**
  - `session-brief` 输出：规则总数 + 近两周被实际触发的规则数 + 触发率为 0 的规则清单
  - 验收：`python cli.py session-brief` 里能看到该字段

- [ ] **M6 文档腐烂防护**
  - CI 检查：README/AGENTS 中出现的 CLI 命令名必须全部存在于 `cli.py` 的 parser
  - 验收：故意在 README 写一个不存在的命令，CI 红

- [ ] **G5.1 环境契约固化**
  - 新建 `docs/ENVIRONMENT.md`，落 v1 已实测的 6 条沙箱事实（PS 吞输出 / 代理假 502 / SSL 兜底 / MinerU 冷启动 42s / GUI 进程生命周期 / safe-delete 开关）
  - 验收：README 引用该文件

---

## P2 — 业务铺开前

- [ ] **M4 存量反馈消化**
  - 明确存量来源：v1 的 `E:/Idea/*/researcher-decision.json`（29 个，verdict 全缺失）
  - 提供 `feedback-import-v1` 命令：把 v1 交付目录导入 v2 pool（verdict 留空待研究者回填）
  - 落实 v2 AGENTS 第 5 条：回填优先于新增供给
  - 验收：`feedback_stats().coverage > 0`

- [ ] **R9 占位数据落位**
  - `knowledge/gap-map.md` / `living-queries.json` / `feasibility_profile.json` 当前是从 v1 抄的占位（"种子待收口"、"光电学院（平均画像）"）
  - 要么填成真实数据，要么删除并在 canon 里标注 "unpopulated"
  - 验收：文件内容不含"待收口"类占位词

- [ ] **G4.6 规则-测试可追溯**
  - canon 每条规则带一个 `test_ref` 字段，指向覆盖它的测试
  - 验收：`validate` 能报出"无测试覆盖的规则"

- [ ] **建立十角度自查方法**
  - v1 的 `project-deep-review-20260914.md` 是元层面能力，v2 应固化为每个里程碑的固定动作
  - 验收：`docs/` 下有里程碑自查模板
