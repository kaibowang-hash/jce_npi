# 领域模型与状态约束

## 1. 聚合边界

### EngineeringProject
项目上下文根。包含项目类型、客户/产品关联、目标 SOP、团队、Gate 实例、健康度和对象索引。项目不能直接拥有 ERPNext 交易明细，只保留关联和只读投影。

### GateInstance
阶段门实例。持有模板版本、交付物要求、证据引用、阻断、会签、豁免和不可变决策快照。证据引用必须指向具体对象版本。

### DesignItem / DocumentRevision / Baseline
设计对象与文件版本。发布后不可覆盖；Baseline 固定一组版本与哈希。任何下游 Trial/Gate 应引用 Baseline/Revision，而不是“最新文件”。

### ToolingDevelopment
Tooling 开发聚合。覆盖所有权、规格、设计修订、制造计划、供应商、ERP 采购投影、试模、问题、验收和资产移交。

### Trial / TrialRound
Trial 是一组试模计划和目标，TrialRound 表示 T0/T1/T2… 实际轮次。轮次提交时冻结输入版本、参数、样件、缺陷和结论。

### NpiReadiness
以模板实例化的就绪项、证据、阻断和评分。评分不能掩盖阻断；有 P0 阻断时状态不能是 Ready。

### ChangeImpactCase
引用 ERPNext 正式变更编号，管理工程影响对象、任务包、验证、Gate 复审和生效证据。

### ExecutionRequest
NPI 对 ERPNext 的正式执行意图。状态与业务批准分离；包含输入快照、幂等键、目标操作、校验、ERP 返回、失败和重试。

## 2. 稳定身份

所有跨系统可共享对象使用：
- `global_id`: UUID，首次创建后不可变；
- `source_system`: `NPI_ONE` / `ERPNEXT`;
- `source_object_type`;
- `source_object_id`;
- `external_refs[]`;
- `business_code`：人类可读编码，允许按受控规则变化；
- `version`：乐观并发版本；
- `last_changed_at/by`.

不得以名称、附件 URL 或可变业务编号作为唯一同步键。

## 3. 状态机

### 项目
`draft → proposed → active → on_hold → completed/cancelled`

- G1 通过后进入 active。
- completed 前必须 G7 完成或有批准的例外。
- cancelled/closed 对象只读；恢复需受控动作。

### 设计修订
`draft → in_review → approved → released → superseded/obsolete`

- released 后不可编辑。
- 新修订通过 `revise` 命令创建。
- supersede 必须引用替代修订和生效点。

### Tooling
`draft → feasibility → design → manufacturing → trial → acceptance → transferred → closed`
另有 `on_hold/cancelled`。不同项目类型可跳过阶段，但跳过规则来自模板并留痕。

### Trial Round
`planned → prepared → running → analysis → submitted → approved/rejected/cancelled`
- prepared 后锁定计划输入；
- running 可记录实际；
- submitted 后冻结；
- rejected 不是删除，可克隆到下一轮。

### Execution Request
`draft → validated → queued → processing → succeeded`
失败分支：
`failed_retryable → queued` 或 `failed_final`
还可 `cancelled`；processing 后的取消由目标系统能力决定。

## 4. 通用工作对象

风险、问题、行动、决策不是四套完全割裂的页面，而是统一 `WorkItem` 视图与不同语义：
- `kind`: risk / issue / action / decision_request;
- `context_type/id`;
- `owner`, `due_at`, `severity`, `blocking`;
- `status`;
- `source/related evidence`;
- 转换关系（风险发生→问题；问题→行动；争议→决策）。

审计中仍保留原类型和状态规则。

## 5. 不变量

- Gate 决策快照不能引用可变“最新版本”。
- Tooling 验收前必须有有效设计/制造/试模和重大缺陷处理结论。
- Trial Round 不能同时属于两个 Tooling。
- 正式质量结果的真值来自 ERPNext；NPI 只保留引用、投影和门禁解释。
- ERPNext 正式 Item/BOM/Asset 编号只有成功 Execution Request 才能写入映射。
- 任何映射变更必须审计；同一 global_id 不得映射到多个相同类型正式对象，除非领域明确允许（例如复制模）。
- 删除优先转为作废/取消；发布、批准、执行过的对象不得物理删除。
