# 使用说明

这是一个“先约束、后规划、再逐任务实现”的 Codex 执行包。它不是让 Codex 一次性生成整个系统的提示词。

## 当前仓库恢复前置

本仓库已经完成多个 Phase，不能从 M0 重启。新会话必须先按
`implementation/AUTOPILOT_CONTROLLER.md` 的恢复协议读取
`PHASE_STATUS.yaml`、`NEXT_ACTION.md`、`LAST_RUN.md` 和当前 Requirement
Anchor；聊天记忆不构成状态事实。

2026-07-25 的 additive reconciliation 已用 281-ID typed trace 取代旧的
Pack-only completeness 结论，但不回写既有 Gate 证据。R1 bridge 完成前，
P5-01 产品任务保持 checkpointed/held。

品牌开发只允许使用 `docs/Brand Asset/Brand Asset Instruction.csv` 和同
目录五个精确 SVG。不得从外部寻找、重画或替换 LaunchFlow/JCE 标志；
稳定 `NPI_ONE`、`ERPNEXT` 和 `/api/npi/v1` 不因显示品牌变化。

## 推荐投入仓库的方式

1. 将本包内容复制到目标代码仓库根目录并提交为基线。
2. 保留 `AGENTS.md`、`GOAL.md`、`contracts/`、`docs/`、`implementation/` 和 `.agents/skills/` 的目录层级。
3. 首轮只发送 `prompts/00_MASTER_GOAL_PROMPT.md`。
4. 只批准 M0。评审 Codex 输出的事实、ADR、架构差距和任务拆分。
5. 之后每次复制 `prompts/02_MILESTONE_EXECUTION_PROMPT.md`，替换一个任务 ID；一个任务一个 worktree/PR。
6. UI 类任务先走 M1 原型和可用性验收，不要直接做后台 DocType 页面。
7. 每次合并前执行 `.agents/skills/release-gate/SKILL.md`。

## 资料优先级

发生冲突时使用 `AGENTS.md` 和
`docs/specification/SPEC_INDEX.md` 当前记录的权威顺序；不要在本文件
维护第三套顺序。

不得为了赶进度跳过冲突说明。


## V1.2 强制基线

任何 UI 工作开始前，必须阅读 `design/UI_VISUAL_BASELINE.md`、`design/design-tokens.json` 和 `docs/UX_INTERACTION_SPEC.md`。任何显示文案变更前，必须阅读 `docs/LOCALIZATION_SPEC.md` 和 `contracts/terminology-allowlist.yaml`。

V1.2 的两条不可妥协基线：
1. Siemens iX Classic Light / 经典西门子工程软件是唯一 UI 基线；单主色、方正、平面边界、紧凑树表和稳定分栏。
2. 英文是唯一源语言；简体与繁体中文通过同一 Frappe 翻译事实源完整输出；普通语言混用为发布阻断。
