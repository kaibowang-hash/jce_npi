# 总体架构

## 1. 上下文

NPI One 与现有 ERPNext 是两套独立业务系统：
- 独立域模型、Site、数据库和发布节奏；
- 可共用基础设施、身份提供方和运维平台；
- 只通过受控 API / 事件交互；
- 不以数据库复制或跨库 SQL 集成。

## 2. 逻辑组件

### 2.1 NPI Web App
React + TypeScript。负责 Siemens 式工业 App Shell、领域工作区、状态呈现和客户端交互。只调用 NPI BFF/领域 API，不直接持有 ERPNext 服务密钥。所有视觉通过本地 token/adapter 收敛；所有文案通过本地 `t()` 适配器复用 Frappe 语言解析与翻译目录。

### 2.2 NPI Domain App
运行于独立 Frappe Site。负责项目、Gate、设计版本、Tooling、Trial、NPI、协作、权限、审计和领域规则。可以使用 DocType 作为持久化模型，但 API 与 UI 应以领域对象和用例为边界。

### 2.3 BFF / Domain API
统一 `/api/npi/v1`：
- Query：为页面返回聚合后的 ViewModel；
- Command：执行有业务语义的动作；
- 长任务返回 operation/request ID；
- 使用明确错误码、版本/ETag 和 trace ID；
- 原始 Frappe REST 只限内部管理或受控低层服务。

### 2.4 Integration App
在 NPI 侧维护 Execution Request、Outbox、Inbox、ID Mapping、重试、死信、回放和对账。ERPNext 侧提供最小权限 API 和 Webhook；复杂写入封装为 ERPNext 自定义 App 的命令接口。

### 2.5 ERPNext
保留正式交易和主数据。NPI One 可显示只读摘要和深链接，但不能重新实现其完整执行界面。

### 2.6 Translation Adapter
英文源字符串、Frappe 翻译目录与 React catalog 使用同一事实源。使用部署版本的 Frappe 官方翻译机制与字符串提取流程：v15 及更早版本通常为 CSV，v16 起可使用 Gettext PO/MO，且自定义 App 可继续使用 CSV；M0 确认实际版本、选用格式、语言代码和构建命令。生产构建对核心页面执行缺失翻译和混合语言阻断；API 使用稳定错误码和命名参数，显示层本地化。

### 2.7 文件与对象存储
文档元数据、版本、审批、基线在 NPI 域。工作文件可位于对象存储；正式发布文件按既定 DMS/ERPNext 文件策略归档。保存哈希、MIME、大小、病毒扫描和访问审计。

## 3. 请求模式

### 同步查询
NPI BFF 根据本地投影返回页面数据。必要的 ERP 当前状态通过短时缓存或服务端查询获取，不能让页面因多次跨系统调用而碎片化。

### 同步命令
仅用于需要立即校验并获得结果的低延迟动作。必须带：
- `request_id`
- `idempotency_key`
- 调用者和权限上下文
- 业务对象 `global_id`
- 期望版本
- trace ID

### 异步执行
正式发布、批量创建 Item/BOM、资产移交等：
1. 领域事务写业务状态和 Outbox；
2. worker 发送至 ERPNext；
3. ERPNext 按幂等键处理；
4. 结果进入 Inbox；
5. NPI 更新 Execution Request 和投影；
6. 失败重试，超过阈值进入 DLQ；
7. 运维可查看、修复并按原消息回放。

## 4. 一致性

不追求跨系统分布式事务。使用最终一致性和显式状态：
- NPI 业务动作可处于 `pending_erp_execution`；
- ERPNext 成功后进入 `executed`；
- 失败进入可重试或需人工状态；
- 用户清楚看见“工程批准”和“ERP 正式执行”不是同一时刻；
- 对账发现差异时创建异常，而不是静默覆盖。

## 5. 身份与权限

- 优先统一身份提供方与 SSO；服务调用使用独立服务账号/密钥。
- 领域权限按公司/工厂、项目、角色、对象关系和状态综合判断。
- 前端隐藏不能替代后端授权。
- 外部用户采用独立角色和项目级授权，不能进入 ERPNext。
- 高风险命令记录操作者、代理身份、输入摘要、结果和 trace。

## 6. 可观测性

统一日志字段：
`trace_id, request_id, event_id, global_id, source_system, target_system, actor, operation, result, duration_ms`

必须提供：
- API 延迟/错误率；
- 队列深度、重试、DLQ；
- 同步滞后和对账差异；
- 关键 Gate/发布/试模操作审计；
- 用户可见 operation status；
- 敏感数据脱敏。

## 7. 性能目标（M0/M1 校准）

初始目标：
- 典型聚合页面 P95 服务端响应 ≤ 1.5s；首屏可交互 ≤ 3s（企业内网标准桌面）。
- 列表过滤/翻页 P95 ≤ 1.0s。
- 普通命令确认 P95 ≤ 2s；长任务 2s 内返回 operation ID。
- 大附件独立上传，不占用业务请求超时。
- 关键页面支持 200 个并发业务用户的基线测试；最终指标在 M0 根据实际规模调整。

## 8. 部署建议

- `npi.company.com`：NPI Web + NPI Frappe Site/DB；
- `erp.company.com`：现有 ERPNext Site/DB；
- 反向代理/WAF、SSO、对象存储、Redis/queue、监控和备份；
- 可以同一集群，但资源、数据库、密钥、备份和恢复边界独立；
- 非生产环境使用脱敏数据和独立 ERPNext sandbox。

## 9. 架构决策门禁

以下必须 ADR：
- Siemens 式设计系统/前端框架、token、翻译适配器或重大升级；
- API 风格和版本策略；
- 身份/SSO；
- 文件存储；
- ERPNext 命令接口和重试语义；
- 新基础设施/生产依赖；
- 状态机或数据主责变化；
- 数据迁移和历史导入策略。
