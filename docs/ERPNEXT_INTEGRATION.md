# ERPNext 集成与共享业务对象规格

## 1. 核心原则

“开发端和 ERPNext 端共享”定义为：
- 一个逻辑业务对象；
- 在两端存在面向各自角色的视图/记录；
- 通过 `global_id + mapping` 关联；
- 每个字段只有一个主责端；
- 正式交易由 ERPNext 执行；
- NPI One 显示执行状态和只读结果；
- 任何反向变化通过事件/对账同步，不自由互相覆盖。

## 2. 共享对象类别

### 2.1 ERP 主责、NPI 投影
客户、供应商、正式 Item、正式 MBOM、PO/PR/Invoice 状态、Quality Inspection/NCR、模具资产/位置/维护、生产订单、正式变更号。

### 2.2 NPI 主责、ERP 摘要/链接
Engineering Project、Gate、设计基线、Tooling Development、Trial Round、NPI Readiness、项目问题和工程行动。

### 2.3 分阶段主责
- 工程临时 Item/EBOM：NPI 主责；发布后 ERPNext 正式 Item/MBOM 主责。
- Tooling：开发/设计/试模 NPI 主责；验收后的资产/维护 ERPNext 主责。
- 文件：工程工作版本与基线 NPI 主责；正式受控发布归档按公司 DMS/ERPNext 策略。
- 变更：ERPNext 主责正式 ECR/ECO/ECN；NPI 主责工程影响执行和验证。
- 质量：试模缺陷 NPI 主责；正式检验/NCR/CAPA ERPNext 主责。

## 3. 字段级规则

每个共享对象定义：
- `field_path`
- `owner_system`
- `editable_in`
- `sync_direction`
- `conflict_policy`
- `effective_stage`
- `sensitivity`
- `audit_required`

默认冲突策略：
- 主责端覆盖投影端显示值；
- 投影端不得写回主责字段；
- 尚未映射正式对象的工程草稿可在 NPI 修改；
- 发布或执行请求开始后，相关输入锁定；
- 对账差异创建 Integration Exception，不自动强制覆盖敏感字段。

机器可读基线见 `contracts/data-ownership.yaml`。

## 4. Execution Request

正式动作示例：
- `create_item`
- `update_item_engineering_fields`
- `create_or_update_mbom`
- `create_purchase_request`
- `create_or_update_tool_asset`
- `publish_controlled_file_reference`
- `request_quality_inspection`
- `update_project_handover_status`

每个请求包含：
- request/global/idempotency ID；
- 目标 ERP 操作和 API 版本；
- 发起对象/版本；
- 输入快照及哈希；
- 主责字段列表；
- 预校验结果；
- 操作者/批准证据；
- 状态、重试次数、下一重试；
- ERP 返回编号/版本；
- 错误分类、用户信息、技术详情和 trace。

## 5. 预校验

发送前至少校验：
- 权限和批准状态；
- 输入对象版本未改变；
- 必需映射存在；
- ERPNext 主数据存在/有效；
- 编码/单位/税务/公司/工厂上下文完整；
- 幂等键未被不同 payload 使用；
- 高风险操作已有 review confirmation；
- 文件完整性/病毒扫描通过。

ERPNext 仍需再次校验，NPI 预校验不能替代目标系统规则。

## 6. Webhook

- 校验 HMAC/签名和允许来源；
- 快速写 Inbox 后返回；
- 按 `event_id` 和业务版本幂等；
- 顺序敏感对象使用版本检测；
- 事件类型/版本不支持时进入隔离队列；
- 敏感 payload 不写普通日志；
- 处理结果可从运维面板查看和回放。

## 7. 重试与对账

- 网络/超时/5xx：指数退避 + jitter；
- 4xx 业务校验：通常不自动重试，进入需人工；
- 429：遵循 Retry-After；
- 幂等冲突：阻断并人工判断；
- 超过阈值进入 DLQ；
- 回放保持原 event/request ID，另记录 replay ID；
- 每日增量对账；关键发布/资产动作可近实时核对；
- 差异有责任人、状态、处置和审计。

## 8. UI 语义

同步状态必须同时显示来源：
- `NPI 草稿`
- `已工程批准，等待 ERP 执行`
- `ERP 处理中`
- `ERP 已完成：ITEM-...`
- `ERP 执行失败，可重试`
- `需要人工处理`
- `投影可能过期`
- `对账差异`

“保存成功”只表示 NPI 事务成功；“ERP 已完成”只有收到目标系统确认才显示。

## 9. 安全

- 前端永不直接调用 ERPNext 或持有服务密钥；
- 服务账号最小权限，按操作拆分；
- 密钥进入 secrets manager；
- 出站域名 allowlist；
- payload schema 验证；
- 防重放和时钟窗口；
- 记录 actor 与 service identity；
- 文件访问用短时授权 URL；
- 外部用户不能触发未经内部批准的 ERP 正式动作。
