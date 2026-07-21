# 设计与技术参考

以下官方资料是 M0/M1 的基线证据；外部资料和版本会变化，Codex 必须在 ADR 中记录实际采用版本、许可证、支持范围、锁定策略和升级影响。

- **Siemens Industrial Experience（iX）Overview / Components / React installation / Theming**：iX 提供工业应用框架、导航、树、工作流、窗格、表单、状态和数据展示等组件，并提供 React 包与 Classic Light/Classic Dark 主题。NPI One 默认采用 React + Classic Light，通过本地 adapter 和公司主题覆盖；不使用仅限 Siemens 官方产品的 Corporate Brand Theme、logo 或专有字体。
- **Frappe Framework Translations**：显示 source 使用英文文字面量并通过 `_()` / `__()` 标记；自定义 App 按部署版本使用 Frappe 官方 CSV 或 Gettext PO/MO 流程，并复用其字符串提取与用户语言解析；v16 起支持 PO/MO，自定义 App 仍可继续使用 CSV。NPI One 的 React catalog 必须与该翻译事实源一致。
- **Frappe Framework**：DocType、权限、审计、后台任务、REST API 与 Webhook。NPI One 前端不直接暴露原始 DocType CRUD。
- **ERPNext**：正式主数据、采购、库存、生产、质量、模具资产、成本和现有自定义模块的主系统。
- **OpenAI Codex**：仓库级 `AGENTS.md`、Skills、逐任务执行和可验证交付。实施时以官方文档当前版本为准。

参考设计系统的公开结构与交互模式不等于复制第三方品牌资产。任何组件采用或替换均需经过许可证、安全、维护、体积、无障碍和可回滚性评审。
