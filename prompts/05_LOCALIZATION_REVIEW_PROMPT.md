# 语言与翻译评审 Prompt

使用 `frappe-i18n` 和 `release-gate` skills 评审 `[TASK_ID / PR / 页面 / 消息流程]`。本轮只评审，不自行降低门禁。

必须读取：
- `docs/LOCALIZATION_SPEC.md`
- `contracts/terminology-allowlist.yaml`
- 已批准的 Frappe 版本、语言代码和翻译格式 ADR
- 本次 translation catalog diff 与测试日志

逐项验证：
1. 所有显示文案的 source 是否为可提取的英文文字面量；
2. Python/Frappe JS/React 是否分别使用 `_()`、`__()`、本地 `t()`；
3. 是否存在 JSX/TSX、模板、配置或第三方组件中的硬编码显示文字；
4. 简体中文和繁体中文是否完整覆盖本次触及核心流程；
5. 中文界面是否残留白名单之外的普通英文；英文界面是否残留普通中文；
6. `Tooling`、`Gate`、`Trial`、`Worklist`、`Workspace` 等是否按词表翻译，而非混合显示；
7. 占位符、context、HTML/Markdown 转义和复数/条件消息是否一致；
8. 日期、数字、金额、单位、时区和列表是否按 locale 格式化；
9. 错误、通知、邮件、打印、导出和异步失败是否也经过同一翻译目录；
10. 是否依赖缺失翻译回退英文进入生产。

输出：`PASS` 或 `BLOCKED`、证据路径、缺失 source、混用位置、术语冲突、最小修复清单。任何核心页面普通语言混用或核心翻译缺失均为 `BLOCKED`。
