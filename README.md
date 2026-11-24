# qa-agent — 测试专项 Agent（Python 路线，定版 2026-11-22）

为测试岗位求职准备的作品：输入需求 / 目标网址 / OpenAPI，自动出测试策略、
生成可执行 pytest + Playwright 用例、真跑、失败自愈与分类、输出 Allure 报告。

技术栈：Python 3.11+ + LangGraph 编排 + Playwright MCP 执行 + pytest + Allure，
fishzjp/qa-skills 做技能层。

## 第一个里程碑（Day 1–2）：跑通 1 条可执行用例

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
pytest tests/test_saucedemo_login.py -v
```

Windows（PowerShell）对应写法：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
pytest tests/test_saucedemo_login.py -v
```

通过标准：登录成功进入商品页，`reports/` 里有 trace + 截图。

## Day 3–4：Planner→Generator 已接线（LangGraph，确定性生成）

`python -m qa_agent.graph` 跑通 Planner → Generator → Executor → Reporter，
不需要 LLM key：Planner 读 `cases/saucedemo-login.yaml`，按等价类出策略
（登录成功 / 密码错误 / 锁定用户 / 用户名为空，共 4 条）；Generator 渲染出
`tests/generated/test_saucedemo_login_generated.py`（参数化 1 个用例函数 × 4 组数据）；
Executor 干跑只做 `pytest --collect-only`，Reporter 写 `reports/summary.json`。

```bash
python -m qa_agent.graph --case cases/saucedemo-login.yaml --dry-run  # 不用浏览器可验
python -m qa_agent.graph --case cases/saucedemo-login.yaml            # 真跑，需 Chromium
pytest --collect-only -q   # 应收集到 5 条：手写 1 条 + 生成 4 条
```

注意：生成用例在 VM 里只验到 collect-only（returncode 0），真跑是否变绿仍需
在你电脑上（或 CI）跑，`--browser-channel chrome` 备用跑法同样适用。
报错文案三条已对过公开来源：密码错误 / 锁定 / 用户名为空的
"Epic sadface: …" 原文。Healer（Day 8–10）与 Analyzer（Day 11–12）仍是桩。

如果 `playwright install chromium` 下载失败（网络受限），而你电脑上已经装了 Chrome，
可以跳过下载，直接用本机 Chrome 跑（`--browser-channel` 是 pytest-playwright 自带参数，
这边已确认存在；这条备用跑法在我这台 VM 上没法验证，因为 VM 里没有可用的本机 Chrome）：

```bash
pytest tests/test_saucedemo_login.py -v --browser-channel chrome
```

## 2 周 MVP 节奏

- 第 1 周：跑通闭环 — Day 1–2 搭结构跑通首条用例；Day 3–4 Planner→Generator
  自动生成 5–10 条用例并执行；Day 5–7 接 Allure + GitHub Actions，PR 自动跑。
- 第 2 周：面试差异 — Day 8–10 加 Healer（故意改页面元素验证自愈率）；
  Day 11–12 加 Analyzer 失败分类；Day 13–14 换 the-internet.herokuapp.com
  再验一遍，录 1 分钟 Demo，README 放架构图 + 指标表。

## 结构

```
qa-agent/
  src/qa_agent/
    state.py        # 全局状态：需求 / 用例 / 结果 / 修复记录
    graph.py        # LangGraph 主图（Day 3 起接线，Day 1 先跑单测）
    agents/         # Planner / Generator / Executor / Healer / Analyzer / Reporter
    tools/          # playwright_mcp.py / allure_tools.py
  tests/            # 生成出来的 pytest 用例
  skills/           # qa-skills 技能层（第三方代码，安装前先读仓库文件）
  cases/            # 输入：需求文本 / 目标网址 / OpenAPI
  reports/          # Allure + trace + 截图，不进 git
```

## 技能层安装（Day 3 前做，先读仓库再装）

fishzjp/qa-skills（MIT，13 个测试技能，中文指令，需 Python 3.9+ 与 Playwright）：

```bash
npx skillfoxx add skills/fishzjp-qa-skills
```

它是第三方代码，安装前先看一遍仓库文件再跑上面命令。

## 许可提醒

bug0inc/qa-agent 是 source-available（Functional Source License 1.1，带两年竞业限制，
之后转 Apache 2.0），思路可学，代码不要抄进这个求职仓库。
