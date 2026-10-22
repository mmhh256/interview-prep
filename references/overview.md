# 简历 × 基座项目 × 面试准备 · 使用说明

> 这是 `interview-prep` Skill 的配套说明。Skill 本体见 `../SKILL.md`；需要核对证据标准或决定本轮读哪个文件时，读 `evidence-contract.md`。

## 它解决什么问题

面试准备常见的三种做法都不牢靠：

- 只背八股 → 一被追问项目细节就露馅。
- 只背简历 → 被问「代码在哪、这段怎么跑」就答不上。
- 让 AI 生成标准答案 → 没有真正理解，临场追问就崩。

本 Skill 把「业务 → 源码 → 原理 → 面试表达」串成一条链，让用户能拿着简历和源码，逐条说清：

> 看什么 · 为什么看 · 看到哪里 · 掌握到什么程度 · 对应哪些八股与追问 · 如何证明真的理解了。

## 四阶段

| 阶段 | 执行卡 | 主要模板 | 过关标准 |
|---|---|---|---|
| 一 材料盘点与项目认知 | `stage-1-intake.md` | `../assets/materials-and-fact-boundary.md`、`../assets/project-map.md` | 能不看答案讲清项目价值与模块配合，并沿代码讲清一条成功链路 + 一个异常分支 |
| 二 简历逐条拆解与源码追踪 | `stage-2-bullets.md` | `../assets/bullet-evidence-card.md`、`../assets/contribution-confirmation.md` | 每条 Bullet 有状态；能说清「做了什么 / 代码在哪 / 我贡献了什么 / 如何验证 / 有何限制」 |
| 三 知识补全与源码实战 | `stage-3-knowledge.md` | `../assets/source-reading-task-card.md`、`../assets/learning-card.md`、`../assets/faq-mastery-checklist.md` | 能不看资料完成「概念 / 定位 / 取舍 / 排障」四类验证 |
| 四 目标岗位与面试冲刺 | `stage-4-job.md` | `../assets/company-research.md`、`../assets/jd-capability-matrix.md`、`../assets/project-story-and-question-bank.md`、`../assets/final-checklist.md` | 能清晰讲述、回应追问，公司事实均有来源或标注假设 |

阶段之间是输入输出关系：阶段一的全景图是阶段二的追踪地图；阶段二的 Bullet 卡和缺口是阶段三的阅读路线来源；阶段一至三的证据是阶段四讲述稿与题库的唯一事实来源。

> 降级：单条 Bullet / 单个概念 / 无源码 / 零材料模拟面试都允许先做最小版本，但必须在台账中标明未建立的阶段，不能宣称已通过。

## 首次使用

1. **准备材料**：简历原文、基座项目（仓库 URL 或可读源码）、目标公司 + JD（没有就明确回复「暂未确定」）、本人真实参与情况。
2. **触发 Skill**：对 agent 说「用 interview-prep 帮我准备面试」或「根据这份简历和仓库准备面试」。
3. **跟随首轮盘点**：Agent 会说明实际读到了什么、哪些读不到，合并追问关键缺口，然后从阶段一开始。

不要跳过阶段一的追问环节。简历、源码、目标岗位、本人经历只要有一项不清楚，Agent 必须先追问，不得编造。

## 每轮如何开始

每次新对话，第一句话可以这样说：

```
继续面试准备。先读取本 Skill 的 evidence-contract.md 和工作区进度台账，
说明当前阶段、已确认事实、未解决问题和下一步任务，再只读取本轮需要的文件。
```

Agent 会：读取台账 → 说明本轮依据了哪些本地资料 → 更新变化的状态 → 执行本轮 1–3 个任务 → 结束前更新台账。

如果换了一个读不到本地文件的环境，Agent 必须如实说明，并请用户上传或粘贴台账，不得假装已经读过。

## 进度与恢复

- **所有状态集中在工作区的 `进度与待确认事项.md`**：已完成任务、新确认事实、待回答的问题、未通过的验收项、下一步任务。
- **所有事实边界和路由集中在 `evidence-contract.md`**。
- **模板即台账**：把 `../assets/` 下的模板复制成工作区副本后填写，更新即代表进度推进。
- 换机器或换对话时，带上整个工作区，进度不会丢。
- 没有变化时不重写文件，只更新真正变化的状态；历史结论保留、不覆盖。

## 证据标记

| 标记 | 含义 |
|---|---|
| `[代码证实]` | 在源码中直接找到实现 |
| `[项目文档证实]` | README / 设计文档等一手文档确认 |
| `[公开资料证实]` | 官方文档、技术博客、可信新闻确认，附链接与日期 |
| `[本人确认]` | 用户明确陈述但暂无外部证据 |
| `[合理推断]` | 基于证据的推断，非事实 |
| `[简历陈述待核]` | 简历这么写，但尚未核实 |
| `[待补资料]` | 缺材料，暂无法判断 |
| `[示例假设]` | 演示用假设，非真实信息 |

**推断不得伪装成事实。**

## 保密

- 不要上传真实客户数据、密钥、Token、内部账号、未脱敏日志或商业机密。
- 公司代码请先脱敏（改包名、域名、密钥、客户名、内部路径）。
- 本 Skill 不索要任何秘密凭据。

## 目录结构

```
interview-prep/
├── SKILL.md                      ← Skill 入口
├── references/
│   ├── overview.md               ← 本文件
│   ├── evidence-contract.md      ← 证据契约 / 文件路由
│   ├── main-prompt.md            ← 原始完整方法论
│   ├── stage-1-intake.md
│   ├── stage-2-bullets.md
│   ├── stage-3-knowledge.md
│   └── stage-4-job.md
└── assets/
    ├── progress-ledger.md
    ├── materials-and-fact-boundary.md
    ├── project-map.md
    ├── bullet-evidence-card.md
    ├── contribution-confirmation.md
    ├── source-reading-task-card.md
    ├── learning-card.md
    ├── faq-mastery-checklist.md
    ├── company-research.md
    ├── jd-capability-matrix.md
    ├── project-story-and-question-bank.md
    └── final-checklist.md
```

原始主 Prompt 已保留在 `main-prompt.md`，本 Skill 是它的可执行化重构。
