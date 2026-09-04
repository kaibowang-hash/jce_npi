# 领域组件使用约束

## 适配层

第三方 UI 组件必须封装在 `frontend/src/ui-adapters/`。业务页面只依赖本地接口，以便主题、可访问性、版本升级和替换。禁止在业务目录到处直接 import 第三方组件。

React 翻译必须通过 `frontend/src/i18n/t()`；不得在组件内自行判断语言或直接写用户可见字符串。

## Siemens 式视觉规则

- 页面和面板使用矩形边界、1px 分隔线和紧凑工具条。
- 0–2px 圆角为默认上限；圆形仅用于头像、单选、状态灯和阶段节点。
- 页面无阴影；浮层才允许轻微阴影。
- 单一工业深青主色；语义色只做小面积辅助。
- 业务首页优先表格、树、分栏和检查器，不做多彩卡片墙。
- 所有组件必须在 1366×768、1920×1080、125% 和 150% 缩放下验证。

## 核心组件

- `AppShell`：固定顶部栏、矩形域导航、全局搜索、通知、环境标识和可选状态栏。
- `PageToolbar`：面包屑、保存视图、筛选、列设置、刷新和上下文动作。
- `ObjectHeader`：对象编号/名称/修订/状态/来源/同步/主动作；紧凑而非卡片。
- `SemanticStatus`：文字 + 小图标/形状 + 可选左边线；不能只靠颜色，不使用彩色药丸。
- `SourceBadge`：NPI / ERPNext / Computed，矩形短标签。
- `SyncBadge`：pending/processing/synced/partial/failure/stale/conflict，矩形短标签。
- `GateTrack`：G0–G7 矩形轨迹和阻断/到期。
- `LifecycleTrack`：Tooling 生命周期。
- `Worklist`：保存视图、服务端筛选、固定表头、树表/split-view、可访问行操作。
- `DockedInspector`：属性、评论、行动、决策、活动和关联；可调整宽度并停靠。
- `EvidencePanel`：具体版本、哈希、审批和预览。
- `VersionPicker`：显示修订、状态、生效、来源和替代。
- `ImpactReview`：高风险命令提交前的影响摘要。
- `OperationStatus`：异步进度、结果、失败、重试和 trace。
- `TreeTable`：工程对象树与多列状态表。
- `EmptyState` / `ErrorState` / `NoPermissionState` / `ConflictState`：文字与操作优先，不使用装饰插画。

## 禁止

- 用卡片墙替代信息层级；
- 多种非语义强调色同时主导页面；
- 普遍使用 8px 以上圆角；
- 每行十几个图标按钮；
- 仅靠 toast 表示长任务结果；
- 在 modal 中嵌套复杂多步表单；
- 以内部 DocType 名作为用户文案；
- 同一状态在不同页面使用不同颜色或译法；
- 把 ERPNext 链接伪装成本地可编辑字段；
- 复制第三方品牌 logo、字体和专有图标包；
- 在中文 UI 中残留普通英文，或在英文 UI 中残留普通中文。
