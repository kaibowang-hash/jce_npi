# AGENTS.md — NPI One / Tooling & New Project Development Platform

本文件对整个仓库生效。新 Codex 会话或 Phase 切换时，必须按 `implementation/AUTOPILOT_CONTROLLER.md` 的恢复协议读取完整恢复文件和当前 Phase 规格，确认实际分支、状态和第一个未完成原子任务；不得以聊天记忆替代仓库事实。原子任务开始时只读取当前任务、相关领域规格、requirement anchor/traceability 索引和适用 Skills。同一原子任务内的小修复不得反复读取完整 DOCX、`GOAL.md`、全部 Pack 或无关领域文档；仅在发现实质歧义、合同冲突、跨领域影响或索引不足时扩大阅读范围。子目录如存在更具体的 `AGENTS.md`，以更接近文件的规则为补充；不得覆盖本文件的安全边界。

## 0. V1.2 持续交付授权与优先级

2026-07-21 总控指令已明确授权：Phase Gate 为 PASS 后自动进入下一阶段，无需逐阶段等待人工批准。该授权仅替代本文件第 5 节及旧 prompts 中的阶段等待规则；产品范围、领域不变量、工业 UI、英文源文案、Frappe 翻译链、安全、数据主责和发布门均不降低。冲突优先级为：总控指令 > V1.2 DOCX > Pack 产品规格/架构/验收 > 合同与 Schema > 本文件与 Skills > 生成计划/决策 > 示例与旧命名。

只允许因总控指令定义的 Hard Blocker 暂停整体执行。缺少生产 ERPNext 凭据不阻断 Mock、合同、Sandbox-ready Adapter、测试和接入文档；禁止连接生产 ERPNext。

### 0.1 P8-07F 生产只读兼容性核对的条件授权

2026-08-29 用户对 `P8-07F` 生产 ERPNext 事实核对给出持续授权，但该授权仅在
`P8-07` Level 3 已 PASS、独立 `P8-07F-GOVERNANCE` transition 的 exact-SHA
ordinary CI 与 Level 3 均 PASS、且后续 `P8-07F-FACTS` 原子任务已由 controller
精确激活后生效。在这些条件全部满足前，本文件其余生产连接禁令继续生效；治理
transition 本身不得建立 SSH、ERP connector、Site 或其他生产连接。

生效后的例外仅允许通过 SSH alias `JCE-Core` 做当前任务所需的严格只读事实采集，
并必须遵守 transition 冻结的 transport/remote-operation allowlist、最小权限、
`BatchMode`、严格 host-key、无 TTY/端口转发/agent 转发、短连接与命令超时、
有限输出、确定性分页、脱敏、provenance 和 checksum。优先复用已验证 inventory，
只在缺失、过期或 checksum/mtime/version 变化时做定向 delta 核对。任一权限不足、
版本不符、输出 shape 未知、敏感值风险、allowlist 漂移或写操作需要都必须立即
停止受影响部分，不得扩权。

该例外不是生产修改授权。始终禁止 `sudo`、生产文件/数据库写入、core/config/
permission/service/queue 变更、migrate/update/restart/reload/clear-cache/scheduler/
console、DocType mutation、webhook/job/adapter/target command、replay/reconciliation
action，以及凭据、cookie、token、private key、site-config secret、endpoint/host/
user/key 或无关业务记录的收集或提交。事实任务只可提交脱敏元数据、源代码事实、
必要汇总、版本、来源和 checksum；实际 ERPNext 定制或 LaunchFlow 产品调整必须
另立获批原子任务。

所有对账以当前已批准的 LaunchFlow architecture、data ownership、OpenAPI/event
contracts 和 P8-01～P8-09 设计/代码为默认正确基线。结论只能使用
`DIRECT_MATCH`、`CONFIG_OR_MAPPING_ONLY`、`MINOR_LAUNCHFLOW_ADJUSTMENT`、
`MINOR_ERPNEXT_CUSTOM_APP_ADJUSTMENT`、`BUSINESS_DECISION_REQUIRED` 或
`NOT_APPLICABLE`；无具体差异证据时必须是 `DIRECT_MATCH`/`NO_CHANGE`。禁止借
事实采集重构、重设计、重命名、合并/拆分领域对象、重做工作流、替换技术栈、
重写权限模型或顺手通用化。最终 implementation/release closeout 前必须在同一
只读边界下完成全量 ERPNext↔LaunchFlow compatibility reconciliation；任何未解决
漂移都阻断 `IMPLEMENTATION_COMPLETE` 与 production-ready。

## 1. 产品使命

建设一套面向注塑企业的新项目开发、Tooling、试模和 NPI 协同平台（产品名暂定 **NPI One**）。系统要像成熟的西门子工业工程软件，而不是 Frappe DocType/单据页面的集合，也不是消费级 SaaS 卡片看板。

核心体验：
- 用户围绕项目、模具、试模轮次、阶段门和变更开展工作，而不是在菜单里逐张找单据。
- 80% 日常工作应从“我的工作”或“项目驾驶舱”完成。
- 关键流程不要求普通用户进入 Frappe Desk。
- 每个批准、发布、阶段门和试模结论都能还原当时的输入版本、证据和责任人。
- ERPNext 继续作为正式制造与经营执行系统；NPI One 不复制一个新的 ERP。

## 2. 目标架构（不可擅自改变）

- **前端**：独立 React + TypeScript SPA，采用工业化 App Shell。视觉、布局、组件密度与交互层级以 **Siemens Industrial Experience (iX) 和经典西门子工程软件**为唯一主要参考；通过本地适配层和公司自有主题实现。默认技术基线为 `@siemens/ix`、`@siemens/ix-react`、`@siemens/ix-icons` + `data-ix-theme="classic"` + `data-ix-color-schema="light"`。不得再以 Frappe Desk、其他企业设计系统或消费级 SaaS 作为视觉基线；不得使用仅限 Siemens 官方产品的 Corporate Brand Theme。
- **后端**：独立 Frappe Site / Database 和独立领域 App；Frappe Desk 只用于管理员、配置和支持。
- **API**：浏览器仅调用 NPI One 的 BFF/领域 API（建议 `/api/npi/v1`）。不得由前端拼接大量原始 DocType CRUD 请求实现业务流程。
- **ERPNext**：正式客户/供应商、Item、MBOM、采购、库存、生产、正式质量、模具资产与维护、成本财务等仍由 ERPNext 主责。
- **集成**：REST 命令/查询 + Webhook + Outbox/Inbox + 幂等 + 重试 + 死信 + 回放 + 对账。禁止跨数据库直接写入。
- **文件**：工作版本、发布版本、基线和正式受控文件分层；发布版本不可覆盖。
- **共享对象**：共享的是一个逻辑业务对象的双端视图，不是两个系统自由双向编辑的副本。字段主责必须在 `contracts/data-ownership.yaml` 中声明。
- **国际化**：英文是唯一源语言；简体中文和繁体中文通过 Frappe 翻译目录产生。用户所选语言下，除 retain 白名单术语/缩写、业务数据、编码和单位外，不得出现任何普通语言混用。实际 Frappe language code 必须在 M0 从部署事实确认。

任何改变上述架构、视觉基线或语言策略的建议必须先形成 ADR，说明原因、替代方案、迁移和回滚影响，并等待人工批准；不得先改代码再补文档。

## 3. UI 视觉硬约束

所有终端用户界面必须同时满足：
- **单一主色**：采用 `design/design-tokens.json` 中的工业深青色；其余以灰、白、深色文字为主。语义色只用于小面积状态/警示，不得做彩色卡片墙。
- **方正经典**：普通面板、输入框、按钮、表格、标签默认 0–2px 圆角。圆形仅用于头像、单选、进度节点等语义本来就是圆形的对象。禁止 8px/12px 大圆角在业务页泛滥。
- **平面边界**：以 1px 边框、分隔线、表格网格和选中条建立层级。默认无阴影；只有浮层可使用轻微阴影。
- **高信息密度**：优先树、表格、分栏、停靠式检查器和工具条。禁止用大面积留白、巨型标题、英雄区、装饰插画、渐变、玻璃效果和 KPI 彩色卡片替代工程信息。
- **经典工程布局**：固定顶部应用栏、稳定左侧域导航、中间工作区、可调整的对象树/表格与右侧属性/协作检查器；操作条与状态条保持位置稳定。
- **克制状态表达**：状态必须有文字和图标/形状；颜色是辅助。大面积背景色仅用于严重错误或安全确认，并采用低饱和浅色。
- **主动作唯一**：一个工作上下文最多一个视觉主动作；其余使用次级按钮、工具条或菜单。

任何违反上述条款的 UI PR 一律 `BLOCKED`，不能以“更现代”“更活泼”“组件库默认样式”为理由放行。

## 4. 语言与翻译硬约束

- 代码、DocType 标签源、前端文案源、消息模板源和 API 用户消息源一律使用英文。
- Python 使用 Frappe `_()`；Frappe JS 使用 `__()`；React 只能通过本地 `t()` 适配器取文案，不允许在 JSX/TSX 中直接写用户可见字符串。
- React `t()` 必须复用 Frappe 的语言解析与翻译目录。必须以部署版本的 Frappe 官方翻译机制、字符串提取和用户语言解析为事实源：v15 及更早版本通常采用 `translations/<language-code>.csv`，v16 起支持 Gettext PO/MO，且自定义 App 仍可继续使用 CSV。M0 必须确认实际版本、选用格式、语言代码和生成/构建命令并形成 ADR。不得另建一套互不相干的翻译库。
- 简体/繁体中文模式下，普通菜单、按钮、字段、帮助、错误、通知、邮件、打印和导出标题必须完整中文；英文模式下不得出现中文。允许项仅限 `contracts/terminology-allowlist.yaml`、用户/客户输入的业务数据、正式编码、文件名和计量单位。
- 不允许依赖 Frappe 的“缺失翻译回退英文”进入生产。开发环境可显示明显的 missing 标记；CI/发布门必须阻断核心页面缺失翻译。
- 禁止字符串拼接形成句子；使用完整句子和命名占位符。禁止把翻译后的文字作为枚举、权限、状态或 API 合同值。
- 状态、动作和术语必须使用受控词汇表；同一概念不能在不同页面出现多个中文译法。

所有终端 UI 任务必须调用 `frappe-i18n` skill，并提交翻译覆盖、混合语言扫描和 英文/简体中文/繁体中文截图或测试证据。

## 5. 工作方式

每次只执行一个被批准的里程碑和一个明确任务。默认采用：
1. 读取任务与证据。
2. 输出范围、非范围、假设、风险、预计修改文件、测试计划和回滚方案。
3. 等待任务被明确批准，或在用户已明确授权该任务时开始。
4. 实现最小完整纵切，不顺手添加“附近功能”。
5. 完成自动测试、类型检查、lint、迁移检查、安全检查、i18n 检查和必要的 UI 证据。
6. 输出变更摘要、验证结果、已知限制和唯一建议的下一任务。

一个 PR / worktree 只服务一个任务。不得把多个里程碑混入同一 PR。

### 5.1 三级验证与修复循环

验证必须按 `implementation/QUALITY_GATE.md` 的 Level 1/2/3 影响分级执行。增量验证只改变执行时机和范围，不改变最终覆盖率、测试内容、PASS 标准、Phase Gate 或最终 Release Gate：

- **Level 1 — Incremental Check**：单个小修复、局部重构或测试修正。只运行修改文件的格式/Lint/类型检查、直接相关的单元或组件测试、受影响页面/语言/视觉案例、必要的定向安全/权限测试，以及 `git diff --check`。
- **Level 2 — Task Gate**：原子任务完成。运行当前模块完整测试、受影响 API/权限/集成/E2E/i18n/视觉测试、当前 Requirement ID 追踪、Task Diff Review 和全部任务验收标准。
- **Level 3 — Full Release Gate**：仅在 Phase 结束、PR 准备合并、生产发布，或公共架构/合同/Schema/认证/权限模型、共享设计系统/翻译框架/核心基础设施变化，或无法可靠界定跨领域影响时运行全仓检查、完整三语言与视觉矩阵、安全/迁移/回滚/恢复、完整追踪及 `release-gate` Skill。

建立并记录 `changed-files → affected-tests` 映射；能可靠界定影响时优先运行受影响测试。公共组件或共享翻译的局部变化先运行受影响页面矩阵；完整视觉矩阵只在 Level 3 或确有全局渲染影响时运行。无法可靠确定影响范围必须升级 Level 3，不得猜测。Level 1/2 通过绝不允许跳过后续适用的 Phase 或 Release Level 3，也不得删除测试、降低阈值或省略最终证据。

同一根因产生的多个失败可在一轮内成批修复；不得每修复一个失败就重启完整 Gate。每批修复后先执行受影响检查，全部相关检查通过后，再在原子任务、Phase、PR 或发布边界运行对应 Gate。

## 6. 防误解分级

### A 类：可逆实现细节
例如变量名、内部函数拆分、小范围布局细节。选择最简单且一致的方案，并在实施说明中记录。

### B 类：需要业务决策
包括状态机、数据主责、字段可编辑端、审批人、阶段门阻断规则、接口契约、权限范围、正式发布语义、术语译法、设计 token 或关键页面布局。遇到歧义必须停止该部分实现，输出 2–3 个选项、影响和建议，不得自行发明业务规则。

### C 类：高风险或不可逆
包括删除/覆盖生产数据、修改 ERPNext 核心、跨库写入、生产迁移、权限放宽、密钥处理、批量同步回放、不可逆 schema 变更。没有明确人工批准与可验证回滚方案时，绝不执行。

## 7. 严格禁止

- 不得修改 ERPNext 或 Frappe 核心源代码；只可通过独立 App、Hooks、Override（经 ADR）和公开 API 扩展。
- 不得让终端用户以 Frappe Desk 表单作为主要产品体验。
- 不得跨数据库直接查询或写入 ERPNext。
- 不得将同一字段设为 Hub 与 ERPNext 双主编辑。
- 不得使用“同步成功”的乐观假象掩盖 ERPNext 执行失败。
- 不得提交硬编码业务 ID、真实密钥、临时管理员权限或测试后门。
- 不得以空实现、永远返回成功、伪造数据、TODO 占位来满足验收。
- 不得吞掉异常或只在服务器日志记录；用户必须得到所选语言的业务错误、可重试动作和 trace/request ID。
- 不得新增生产依赖，除非 ADR 已包含许可证、维护状态、替代方案、体积/安全影响并获批准。
- 不得绕过权限、审计、版本锁和阶段门。
- 不得根据截图臆造字段或流程；以规格、契约、现有代码和真实 API 为证据。
- 不得做未列入当前验收标准的“顺手优化”。
- 不得使用多彩状态卡、渐变、玻璃拟态、强阴影、大圆角、悬浮胶囊导航或消费级插画。
- 不得直接复制 Siemens 商标、专有字体、品牌 logo 或受限资产；只采用公开设计系统的结构与模式，并使用公司自有主题。
- 不得在中文 UI 中出现 `Save`、`Cancel`、`Submit`、`Status`、`Owner` 等普通英文；也不得在英文 UI 中出现普通中文。

## 8. 完成定义

一个功能只有同时满足以下条件才算完成：
- 对应需求 ID 和验收标准可追踪；
- 正常、空数据、加载、无权限、只读、错误、冲突和异步处理中状态均有处理；
- 后端权限和输入验证有效，不能仅依赖前端隐藏；
- 重要状态变化有审计；高风险操作有确认和影响摘要；
- API 有契约测试；关键业务有单元/集成测试；关键 UI 有组件或端到端测试；
- 可访问性基础要求满足：键盘操作、焦点、标签、对比度、非颜色唯一表达；
- 视觉审查确认单一主色、方正边界、工程密度和西门子式布局；
- 紧凑 icon-first 次级动作仅通过仓库本地图标适配层，并具备翻译后的可访问
  名称/tooltip、键盘、焦点、禁用和非 hover 路径；主动作、高风险或含义不明
  的动作保留可见文字；不得出现 GitHub 品牌、直接供应商图标导入或未批准的
  Primer/Octicons 依赖；
- 英文、简体中文与繁体中文页面均通过翻译覆盖和混合语言扫描；
- 没有静默失败、假成功、未处理 TODO 和测试绕过；
- 文档、契约、迁移和回滚说明与代码一致；
- UI 变更提供 英文、简体中文、繁体中文截图或可复现的 story/fixture；
- 在适用的 Task、Phase、PR 或发布边界，按三级验证策略完成对应 Gate；Level 3 边界必须通过 `release-gate` skill。
- 任何 ERPNext 相关实现/发布收尾必须通过 P8-07F 最终全量生产只读 compatibility
  reconciliation：所有 required 依赖与 contracts、ownership、mappings、adapters、
  permissions、tests、deployment/rollback 文档一致；未解决漂移或未验证依赖不得
  标记 `IMPLEMENTATION_COMPLETE` 或 production-ready。该 Gate 不授权任何生产修改。

## 9. 目录约定

- `apps/npi_core`：Frappe 领域 App（如仓库最终采用其他位置，须在 M0 ADR 记录）。
- `apps/npi_integration`：ERPNext 集成 App/模块。
- `frontend/`：React + TypeScript SPA。
- `contracts/`：OpenAPI、事件 schema、数据主责和术语白名单。
- `design/`：设计 token、组件约束和视觉基线。
- `docs/`：产品、架构、UX、本地化、领域和 ADR。
- `implementation/`：路线图、任务和验收映射。
- `.agents/skills/`：仓库内可复用 Codex skills。

M0 完成前不得假定上述目录已经存在，也不得直接创建完整脚手架；先做仓库勘察和 ADR。
