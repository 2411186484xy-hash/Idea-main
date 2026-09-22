# ENVIRONMENT（沙箱实测 6 条，应对已内置在代码里）

> 本文件只记"环境是什么样"，不记阈值（数值单真源仍是 `governance/workflow_authority.json`）。
> 出处：V1 仓只读实测（`AGENTS.md` 调用通道、`outputs/*202609*.md`）+ 本仓 M0 会话复测。

## 1. PS 入口吞 stdout

现象：PowerShell 会话里 `*.ps1` 入口 exit 0 但 stdout 为空（V1 `oc-research.ps1` 沙箱实测，V1-AGENTS 记为"沙箱吞输出"）。
动作：入口只做转发（`os.ps1` → `cli.py`），`cli.py` 启动即 `stdout.reconfigure(encoding="utf-8")`；排障时一律直调 `python cli.py`。
会话写法：命令头一律先设 `[Console]::OutputEncoding=[Console]::InputEncoding=[Text.Encoding]::UTF8` + `$env:PYTHONIOENCODING='utf-8'`（PS5 默认 GBK 会吞非 ASCII 输出）。

## 2. 沙箱代理假 502

现象：会话沙箱带 `HTTP_PROXY/HTTPS_PROXY` 中间人（曾见 `127.0.0.1:49268/7897`）；经代理的 localhost 请求（如 Zotero `:23119`）被吞出假 502（V1-AGENTS 调用通道固化 `--noproxy`）。
动作：`pipelines/search.py::_urlopen_noproxy` 显式 `ProxyHandler({})` 绕行；不断网 raise，只回 ErrorEnvelope。Zotero 通道同样先 bypass 再判离线，不把代理错当服务错。

## 3. SSL 缺省链不可用，certifi 代码内兜底

现象：Windows OpenSSL 缺省 cafile（`C:\Program Files\Common Files\SSL\cert.pem`）不存在，直连 `export.arxiv.org` 报 `CERTIFICATE_VERIFY_FAILED`；显式用 certifi context 即 200 OK（V1 environment-adaptation-checklist P2-1 实测）。
动作：`search.py::_ensure_ssl_cert_env` 从运行解释器解析 certifi 并注入 `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`。**不依赖用户级持久变量**（V1 教训：已启动的会话不生效、venv 重建即失效，见 path-ownership-and-parity-review #3）。

## 4. MinerU 冷启动≥120s，探针降级

现象：`mineru --version` 冷启动约 42s（import torch）；30s 状态探针超时造成假阴性，改为 120s 后复测正常（V1 path-ownership-and-parity-review #2；`.venv-mineru` import client 42.1s 实测）。
动作：`pipelines/pdf.py`（M2c）里 MinerU 只做第二通道，探针超时按冷启动量级设；探针不过不阻断 PyMuPDF 文本层，降级记 `fallback_from`。

## 5. GUI 寿命不可依赖（2026-09-22 复测：写面其实可用，此前记的"离线"是误判）

现象：Zotero 是 GUI 进程，本地 API（`localhost:23119`）随进程存活。沙箱内由命令启动的 GUI 在该命令结束时即被回收；分离启动（`DETACHED_PROCESS + CREATE_BREAKAWAY_FROM_JOB`）同样逃不掉；只有长持有任务能让它跨命令存活。`schtasks.exe` 在沙箱程序黑名单内，做不了真正独立的启动。故「进程不在」是常态而非数据错。
动作：要用写面就先启动 Zotero 再跑三段式。2026-09-22 实测事实：
- **写面可用**，两道闸：缺 `Zotero-Server-ID` 头 → `428`；缺本地 API key → `401`（`POST /api/local/authorize` 弹窗，需人点一次）。授权调用必须放宽客户端超时（`pyzotero._client.httpx2.Client(timeout=900.0)`），否则人未点即 `ReadTimeout`。
- profile 已设 `extensions.zotero.httpServer.localAPI.enabled = true`，无需改动。
- **插件侧载**：`.xpi` 放进 `<profile>/extensions/<addon-id>.xpi` 后 Zotero 只注册为 `userDisabled=true`（不激活）；须在 Zotero **关闭状态**下把 `extensions.json` 中该项改为 `active/seen=true, userDisabled=false`，重启才加载。
- `create_items()` 的返回体不含 title/DOI，写入审计的 dump 必须按 `idea-os:` 标签从库里回读真实条目，否则校验全成空 key。
- 离线仍是预期分支：manifest 照出、写面暂停，绝不把"进程不在"当数据错。

## 6. safe-delete：只删临时态，删前列目录确认

动作：唯一删除入口 `store.delete_tree` 只被 `runs.finish` 调用（收口即删 run 目录）；知识层账本只追加、git 跟踪可恢复，不删。
纪律：删前 `Get-ChildItem` 确认路径；禁碰 `C:\Windows*`、`C:\Program Files*`；测试另有污染守卫（`tests/conftest.py`：真实 knowledge/runs 零写入，违者整席红）。
