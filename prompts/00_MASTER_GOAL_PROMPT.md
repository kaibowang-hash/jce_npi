# 首轮发送给 Codex 的 Goal Prompt

你现在负责接手一个注塑企业的 NPI One 项目。请先完整阅读仓库根目录的 `AGENTS.md`、`GOAL.md`、`README_FOR_CODEX.md`、`docs/`、`contracts/`、`implementation/ROADMAP.md` 与 `.agents/skills/`。

你的当前授权仅限 **M0：发现与决策**。不要开始业务功能开发，不要创建完整脚手架，不要修改数据库，不要安装生产依赖，也不要修改 ERPNext/Frappe 核心。

请执行：

1. 使用 `repo-discovery` skill 勘察仓库、运行方式、测试、CI、现有 Frappe/ERPNext 自定义 App、DocType、Hooks、API、权限和迁移。
2. 区分“仓库事实”“从文档得到的目标”“仍需人工确认的未知项”，不要用假设填空。
3. 画出现状与目标的上下文图、容器图和关键数据流；指出哪些内容已经存在、哪些应复用、哪些需要新建。
4. 盘点 ERPNext 中现有的模具、质量、变更、文件管理对象及可用 API；对每个共享对象提出字段主责和执行边界草案。
5. 输出 ADR 草案，至少覆盖：
   - Siemens iX Classic Light 前端壳、React adapter、主题与专有品牌资产边界；
   - Frappe Site/App 边界；
   - BFF/领域 API；
   - 身份/SSO；
   - 文件与版本；
   - ERPNext 集成可靠性；
   - Frappe 实际版本与语言代码、CSV 或 Gettext PO/MO 翻译事实源、字符串提取/构建命令、React 翻译 adapter 与零混用门禁；
   - 前端测试、后端测试和端到端测试；
   - 观察性和审计。
6. 将 M1 拆成最小、可演示、可测试的纵切任务。每项写明范围、非范围、依赖、验收、测试、风险和回滚。
7. 输出你建议先批准的唯一下一任务，但不要执行它。

必须遵守：
- 不得把产品做成 Frappe 单据菜单集合。
- 不得出现跨库写入、双主字段或假成功同步。
- 不得顺手添加规格之外的功能。
- 任何 B/C 类歧义按 `AGENTS.md` 停止并列出决策选项。
- 输出中引用证据文件路径和代码位置；无法确认就明确写“未知”。


UI 与语言硬约束：任何终端页面必须遵守 Siemens 式单主色、方正、扁平、高密度基线；所有显示文案以英文文字面量为源并通过同一 Frappe 翻译事实源输出；英文、简体中文、繁体中文均不得出现普通语言混用。涉及 UI 使用 `industrial-ux`，涉及文案使用 `frappe-i18n`。
