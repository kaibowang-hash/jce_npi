# 端到端验收与测试策略

## 1. 业务黄金路径

### AT-01 客户来模
创建项目 → 登记所有权/接收检查 → 差异与客户确认 → T0/T1 → 质量结果 → 模具验收 → ERP 资产映射 → G6/G7。

验收：
- 每步能从项目驾驶舱追溯；
- 客户所有权和维修授权不会丢失；
- 重大接收差异阻断试模/验收；
- ERP 资产失败不会显示已移交。

### AT-02 按图新制模具
客户输入 → DFM → Tooling 规格/预算/供应商 → 设计释放 → 制造里程碑 → T0–Tn → 客户批准 → 资产和量产移交。

验收：
- 制造引用的设计修订被锁定；
- ERP PO/成本只读投影；
- Trial 可比较；
- 发布/资产请求幂等。

### AT-03 Gate 复审
G2 通过后客户图纸主版本改变。
验收：
- 原 Gate 快照保留；
- 系统标记受影响 Gate/Trial；
- 自动创建复审和影响行动；
- 未复审前后续受控动作被阻断。

### AT-04 正式质量失败
NPI 中 G6 准备通过时 ERPNext Quality Inspection 更新为失败。
验收：
- Webhook 幂等处理；
- Gate 状态变为需复审/阻断；
- 项目经理和质量收到工作项；
- 不覆盖原质量记录。

### AT-05 ERP 部分失败
EBOM 发布创建 10 个 Item，其中目标系统报告部分成功。
验收：
- 状态为部分成功，不是假成功；
- 已创建映射和失败节点清楚；
- 重试只处理安全的失败节点；
- 对账可验证最终一致。

### AT-06 客户 Tooling List 受控导入

上传一个脱敏 43 列 XLSX，包含插入的标题行、共用 Tooling 分段、多值
外部编号、`New Tooling` 混入编号、`#REF!`、未定义 A/B/C、双射/镶件备注、
一个确定和一个不确定图片锚点。

验收：

- 不依赖固定行号识别数据/分段/共用/汇总区域；
- 预览明确 create/update/skip/错误/待确认；
- `#REF!` 不进入正式产能结果，A/B/C 不被自动解释；
- 共用模只建立 Applicability，复制套数创建独立 physical Set；
- 图片不确定时不自动绑定；
- 每个结果可反查文件/hash/批次/行/列/原值/转换；
- 部分成功不显示完整成功，安全 retry 幂等；
- downstream-used 对象的破坏性 rollback 被拒绝并给出 forward-fix 路径。

### AT-07 共享 UX 与 LaunchFlow bridge

验收：

- 列宽拖动/auto-fit/reset/键盘调整按用户+视图+表版本持久化；
- 折叠导航和 resizable pane 保留项目、选中、筛选、滚动和焦点上下文；
- 字段/附件显示 required/editability/source/lock reason/scan/progress/hash；
- 紧凑 icon-first 动作仅通过批准的本地图标适配层，并具有翻译后的名称/
  tooltip、键盘、焦点和禁用态；高风险/含义不明的主动作保留可见文字，
  且无 GitHub 品牌、直接供应商图标导入或未批准的 Primer/Octicons 依赖；
- LaunchFlow 仅使用品牌 CSV 允许的精确资产/场景，技术身份保持不变；
- favicon、pre-shell loading、dark/light logo、compact source identity 和
  website footer 均有可访问名称与对比度证据；
- `NPI_ONE`、`ERPNEXT` 和 `/api/npi/v1` 的稳定契约值不变；
- My Work inline expansion 仅在 DR-REC-001 批准后纳入。

### AT-08 受控打印与 Released Trial Summary

验收：

- 普通用户从 SPA/BFF 发起，不进入 Desk；
- 输出来自不可变对象/版本快照，含语言、打印人/时间、QR/hash 和审计；
- 未配置/未批准模板或权限时 fail closed；
- Released Trial Summary 包含精确输入、参数、穴位、问题、结论和受控引用；
- ERP/JCE 侧契约只读，不得编辑 NPI Trial 真值；
- 未批准表单、签字、copy numbering 和目标事件名不被冒充为完成。

## 2. UI 状态矩阵

每个核心页面至少验证：
- loading/skeleton；
- 正常；
- 空数据；
- 无权限；
- 只读；
- 部分投影不可用；
- 冲突/版本过期；
- 后端验证失败；
- 异步 queued/processing；
- retryable/final failure；
- 离开未保存保护；
- 150% 缩放和键盘路径；
- 单主色/中性色比例、0–2px 圆角、无页面阴影；
- 英文、简体中文和繁体中文三种 locale；
- 混合语言扫描与缺失翻译。

## 3. 测试层次

- Domain unit：状态机、不变量、Gate、评分、版本和字段主责。
- API contract：OpenAPI 请求/响应/错误。
- Integration：Outbox/Inbox、幂等、重试、DLQ、Webhook 签名、ERP sandbox。
- Permission：角色/项目/对象/字段/外部用户矩阵。
- Frontend component：领域组件、状态和可访问性。
- E2E：黄金路径和高风险动作。
- Migration：升级、重跑、回滚/forward fix。
- Performance：驾驶舱聚合、列表、队列和大文件。
- Security：越权、IDOR、上传、XSS/CSRF、密钥、重放、日志泄漏。
- Resilience：ERP 不可用、队列重启、重复/乱序事件、网络超时。
- Import/Data Exchange：XLSX archive safety、区域识别、映射、公式/图片、
  provenance、partial result、retry、correction artifact、rollback denial。

## 4. 发布阻断

以下任一存在则不允许合并/发布：
- 验收需求无测试或证据；
- 状态机/主责/契约与代码不一致；
- 关键路径进入 Frappe Desk 才能完成；
- 无权限/错误/异步失败状态缺失；
- 假成功、静默 catch、硬编码密钥或测试绕过；
- migration 不可重复或无回滚/forward-fix；
- ERPNext 写入非幂等；
- 发布/批准对象可被直接覆盖；
- P0 安全问题；
- UI 可用性测试出现未关闭的严重误操作。


## 5. 视觉基线验收

每个核心页面的截图/视觉测试必须确认：
- 主要布局为顶部应用栏 + 左域导航 + 中央工作区 + 可选停靠检查器；
- 中性色占主导，只有一个主色；
- 语义色不形成彩色卡片墙；
- 普通组件圆角不超过 2px；
- 面板无阴影，浮层阴影克制；
- 表格/树/分栏承载主要信息；
- 1366×768、1440×900、1920×1080、125% 和 150% 缩放下可操作；
- 1440×900 下核心工作页无需滚动即可同时看到对象上下文、主要动作、
  工作列表和属性区。

以下任一为发布阻断：大圆角卡片墙、渐变/玻璃效果、强阴影、装饰插画主导、Frappe Desk 泄漏、多个非语义强调色竞争。

## 6. 国际化验收

- 所有显示 source 均为可提取英文文字面量，并经过 `_()` / `__()` / `t()`；
- 简体中文和繁体简体中文和繁体中文 catalog 覆盖所有触及的核心文案；
- 简体/繁体简体/繁体中文 UI 的普通英文残留为零（按术语白名单排除）；
- 英文界面 的普通中文残留为零（业务数据除外）；
- 占位符、复数/条件消息和错误代码测试通过；
- 日期、数字、金额和时区按 locale 正确；
- 英文/简体中文/繁体中文 E2E 均覆盖至少一个正常、一个错误和一个异步失败流程。
