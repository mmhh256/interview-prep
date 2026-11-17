# Evidence and Evaluations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复面试准备规则冲突，并提供不混淆静态检查、模型输出与语义评分的可复现验证。

**Architecture:** 保留 Markdown Skill，集中定义三条状态链与材料信任边界。标准库工具分别做静态检查、模型采集、人工/评审者语义评分，CI 不将未评分输出当行为通过。

**Tech Stack:** Markdown, Python >= 3.8 标准库, GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-11-17-evidence-and-evaluations-design.md`

## Global Constraints

- 不引入服务或第三方 Python 依赖；Python >= 3.8，支持 Windows 与 Linux。
- `assets/` 是只读模板源；所有个性化状态和产物写入已确认的当前用户工作区。
- F、C、M 不互相推导；失效保留历史，只影响有关记录。
- 简历、JD、源码与网页中的指令只是待分析数据，不覆盖教练规则。
- 静态检查与真实模型行为评测分开运行、分开报告。
- 预期行为按语义和证据判定，不用关键词/正则决定行为通过。
- 不伪造模型输出、跨模型结论、历史迭代、GitHub Release 或用户已掌握记录。
- 当前环境无独立子代理工具；按用户“追加后开始”要求直接在修复分支执行。

## Review Focus

- 材料里伪造的高优先级指令不能进入系统角色；采集输入不包含评分标准或预期答案。
- 零凭据、401、空响应、半途失败和未评分不能统计为行为通过。
- 不同来源/版本/用例的评分文件不能与当前运行混用；重复或漏项判定须拒绝。
- 无源码、无贡献证据、照读参考答案必须分别影响 F/C/M，而不一刀切或虚报 L2/L3。
- 已确认经历/独立表现与用户明确要求参考答案是正向控制，不能因防虚构一律拒绝。

---

### Task 1: 建立分离的验证工具与固定回归输入，记录基线

**Files:**
- Create: `scripts/eval_support.py`, `scripts/check_static.py`, `scripts/run_behavior_eval.py`, `scripts/score_behavior_eval.py`
- Create: `tests/test_static.py`, `tests/test_behavior.py`, `tests/test_scoring.py`
- Create: `evals/cases.json`, `evals/fixtures/search.py`, `evals/fixtures/search_v2.py`
- Modify: `.gitignore`（保留原有系统文件、凭据与私人准备材料规则）

**Interfaces:**
- Produces: `check_repository(root: Path) -> list[dict]`，每条静态问题含路径与原因；CLI 报告 `kind=static`。
- Produces: `load_cases(path: Path) -> list[dict]`，唯一用例 ID、输入轮次、fixture 与逐项语义 criteria。
- Produces: `build_messages(root: Path, case: dict, variant: str, revision: str) -> list[dict]`，Skill 在 system，全部项目材料在 user，criteria 不传入模型。
- Produces: `run_evaluation(root, cases, model, base_url, api_key, api, variant, revision, repeats, timeout) -> dict`，`kind=behavior`，保留逐轮输出与失败；缺 key 为 `not_run`。
- Produces: `score_run(run: dict, cases: list[dict], judgments: dict) -> dict`，只验证证据完整性并汇总外部语义判定；未评分/未运行不计通过。

- [x] **Step 1: 先写工具边界测试**：临时 Markdown 中写入模板路径被发现而读取模板不报错；坏链接报错；用例路径越界/重复 ID 被拒绝；项目伪造 system 文本仍在 user；criteria 不进入模型输入；零 key、401、空输出、部分轮次失败不是完成；错哈希、重复/缺失评分、伪造引用被拒绝。
- [x] **Step 2: Run RED**：`python -m unittest discover -s tests -v`。Expected: 工具尚未实现的测试失败；将命令及原因写入任务台账。
- [x] **Step 3: 实现最小标准库工具和合成 fixture**：覆盖模板写入、未知贡献、先答后教、误标掌握、可选任务、F/C/M 失效、四类材料注入、L2/L3 正向控制、全量答案例外。
- [x] **Step 4: Run GREEN**：`python -m unittest discover -s tests -v`。Expected: 全部工具测试通过；模拟 HTTP 服务只验证采集器，不列为真实模型结果。
- [x] **Step 5: Run 基线**：`python scripts/check_static.py --output .superpowers/static-baseline.json`。Expected: 原始阶段文件的模板写入目标被发现，exit 1。
- [x] **Step 6: 在修改 Skill 前尝试真实无 Skill / 原始版本场景**：已各请求一次，均 HTTP 401；每次所选 3 场景 × 5 个计划样本中，1 个请求错误、14 个因授权失败未运行。没有完成任何模型输出，不评分，也没有五次执行证据。
- [ ] **Step 7: Commit**：`git add scripts tests evals .gitignore; git commit -m "test: add separate static and behavior evaluation tools"`。

### Task 2: 统一执行规则、三条状态链与模板

**Files:**
- Modify: `SKILL.md`, `references/evidence-contract.md`, `references/overview.md`, `references/main-prompt.md`, `references/stage-1-intake.md`, `references/stage-2-bullets.md`, `references/stage-3-knowledge.md`, `references/stage-4-job.md`
- Modify: `assets/*.md`（全部 12 份模板）
- Create: `references/maintenance-checklist.md`

**Interfaces:**
- Consumes: Task 1 的用例输入与独立静态报告。
- Produces: F/C/M 统一状态契约、工作区写入路由、默认先答后教、可选任务启用条件和数据指令隔离；供 Task 3 的模型输入与评分引用。

- [x] **Step 1: Read RED evidence**：基线静态报告复现 6 处模板冲突；无 Skill / 原版 API 均 401，只有静态复现，行为基线未完成。
- [x] **Step 2: 修改证据契约与入口**：三条链字段、等级标准、独立失效、联合门槛、工作区与数据指令隔离。
- [x] **Step 3: 修改四阶段、使用说明与主 Prompt**：统一路由、先答后教、贡献待核、明确启用场景；当前主 Prompt 消除旧冲突，历史原文在 Git 保留。
- [x] **Step 4: 更新 12 模板及维护验收**：分表或独立卡关联且有证据/版本；未知不推归属；最终清单只验收用户，未启用场景不适用。
- [x] **Step 5: Run GREEN**：34 项工具单测通过，窄静态检查 0 issues；语义一致性为作者自审，独立行为评测未完成。
- [ ] **Step 6: Commit**：`git add SKILL.md references assets; git commit -m "fix: unify workspace evidence and coaching contracts"`（尚缺 Git 作者与推送授权）。

### Task 3: 示例、语义评分与分开的实际结果

**Files:**
- Create: `evals/README.md`, `evals/examples/training-dialogue.md`, `evals/reports/static.md`, `evals/reports/behavior.md`
- Create: 仅实际存在的脱敏采集记录及评分，置于 `evals/runs/`（不提交凭据、私人材料或模拟服务结果）。

**Interfaces:**
- Consumes: Task 1 采集/评分 schema，Task 2 当前 Skill。
- Produces: 可复现命令、语义评分流程、完整示例与适用范围、静态/真实执行状态单独报告。

- [ ] **Step 1: 编写完整训练对话**：项目/源码合成输入、先问、错误回答、定向补充、独立复述、取舍/故障追问与 F/C/M 结论；明确这是规范示例而非真实模型运行。
- [ ] **Step 2: 用固定场景重新运行当前版本**：与控制/原始版本分别保存，记录请求/实际模型、时间、版本和采样限制；可用模型分别报告，没有第二个模型就标未运行。
- [ ] **Step 3: 对实际完成的每个场景逐项语义评分**：读完整输入与原文，提供引用/遗漏范围及理由，标评分者类型；没有实际输出不评分，不通过字符串匹配评分。
- [ ] **Step 4: 生成独立报告与指南**：静态报告不含行为通过率；行为报告区分尝试、完成、错误、未运行、未评分、通过、失败和重复样本波动；文本评测不代表工具沙箱安全。
- [ ] **Step 5: Run**：`python -m unittest discover -s tests -v && python scripts/check_static.py`。Expected: 全部通过；模型不可用作为单列限制而非工具测试失败。
- [ ] **Step 6: Commit**：`git add evals; git commit -m "docs: publish evaluation rubrics examples and execution status"`。

### Task 4: CI、版本说明、最终审阅及推送

**Files:**
- Create: `.github/workflows/static-checks.yml`, `.github/workflows/behavior-evals.yml`, `CHANGELOG.md`
- Modify: `README.md`, `SKILL.md` 版本元数据，本计划完成复选框。

**Interfaces:**
- Consumes: Tasks 1–3 工具、规则与报告。
- Produces: 自动静态检查；手动、凭据受控且不自动判通过的行为采集工作流；明确版本声明与公开验证范围的 README。

- [ ] **Step 1: 接入独立 CI**：push/PR 只运行标准库单测与静态检查；行为工作流仅 workflow_dispatch，凭据来自 Secrets，模型参数通过 env 引用，保存原始 trace，不对未评分结果给行为通过结论。
- [ ] **Step 2: 更新 README 与 CHANGELOG**：正确仓库 URL、1.0.3 声明、规则与 F/C/M 链、评测命令、两类报告链接及未验证范围；不宣称补出了历史 Release。
- [ ] **Step 3: Final review**：制作全分支 review package，自审安全边界/报告真实性/路径/状态失效/正向控制；无独立评审工具必须说明自审不独立。
- [ ] **Step 4: Final verification**：`python -m unittest discover -s tests -v && python scripts/check_static.py && git diff --check`。Expected: 全部通过、无空白错误；核对报告与最新真实输出，不遗漏失败。
- [ ] **Step 5: Commit**：提交版本、CI、设计与计划，确认工作树干净。
- [ ] **Step 6: Push**：按用户授权快进合并到 main，推送 `origin main`；若远端改变不强推，核对远端 SHA 与本地 HEAD。

## Skill 编写与验证清单

- [x] 创建覆盖时间、权威、经济/面试压力的固定场景。
- [x] 尝试无 Skill 控制与原始版本；原文记录实际行为或接口阻塞。
- [x] 按实际基线归类失败，不把静态发现伪装成模型失误。
- [x] 保持 name 为字母/数字/连字符；description 仅描述触发场景且以 Use when 开头。
- [x] frontmatter 必需字段齐全、核心原则清晰、证据/工作区/注入关键词可发现。
- [x] 指引形式匹配：状态用结构字段、可选行为用明确条件、纪律规则用反例/红旗。
- [ ] 行为措辞微测有控制与 5+ 重复；不可运行须标阻塞而非完成。
- [ ] 代码/工具有独立文件与解释；完整训练示例单一且可复核。
- [ ] 当前 Skill 场景运行及逐项语义评分，实际失败不隐藏。
- [x] 识别新漏洞、记录反例/常见错误：loopback 代理与携带凭据重定向均 RED→GREEN，规则反例集中记录。
- [x] 不新增无必要流程图；提供快速规则表与常见错误，避免叙事型技能说明。
- [ ] 支撑文件只用于契约、工具、示例、评测与维护资料。
- [ ] 全量测试、最终审阅、提交与用户授权的推送。

## 计划自审

已将五条 Review Focus 分别纳入 Task 1 工具测试、固定输入和 Task 3 语义判定。静态错误基线故意不通过，与采集器单元测试不同；没有真实输出时不得给行为绿色结论。所有跨任务接口沿用同一 F/C/M 契约和 run/criteria schema。
