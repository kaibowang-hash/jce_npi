# 领域模型与状态约束

## 1. 聚合边界

### EngineeringProject
项目上下文根。包含项目类型、客户/产品关联、目标 SOP、团队、Gate 实例、健康度和对象索引。项目不能直接拥有 ERPNext 交易明细，只保留关联和只读投影。

### GateInstance
阶段门实例。持有模板版本、交付物要求、证据引用、阻断、会签、豁免和不可变决策快照。证据引用必须指向具体对象版本。

### DesignItem / DocumentRevision / Baseline
设计对象与文件版本。发布后不可覆盖；Baseline 固定一组版本与哈希。任何下游 Trial/Gate 应引用 Baseline/Revision，而不是“最新文件”。

### ToolingRequirement
项目为什么需要 Tooling 的需求聚合：新制、客户来模、复制、改模、维修或产能补充。持有目标产能、所有权、预算、目标日期和验收标准，但不充当逻辑 Tooling 身份或物理套数。

### ToolingMaster / ToolingApplicability
`ToolingMaster` 是可跨项目、机型、产品和零件复用的逻辑身份。项目通过有版本和生效期的 `ToolingApplicability` 使用它；共用模不得按项目复制 Master。

### ToolingRevision
有版本的设计/制造规格与受控文件集合。状态机和授权来自未来批准的
Tooling policy；释放 Revision 不可覆盖。

### ToolingSet
一套可触摸的物理模具/复制模。每套独立记录序列号、来源 Revision、供应商、状态、位置和 ERP 资产映射。计划复制数量不能替代实体 Set。

### CavityMap / InsertApplicability / ProcessChain
`CavityMap` 将 Revision/Set 的具体穴号映射到 Part Applicability，并记录封穴/启用状态和穴级试验结果。镶件/换镶件、双色/双射/包胶工序通过有版本的结构化关系表达，不写在编号或备注中。

### ProcessBaseline / CapacityScenario
Customer Standard、Trial Actual 和 Approved Process Baseline 是三个不同事实层。Capacity Scenario 以有版本的可用时间、工作日、OEE、良率、节拍、穴数、用量和有效套数计算零件/整机产量、瓶颈和缺口，不在 Tooling Master 上写死结果。

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

### Tooling Requirement / Revision / Set

三个对象必须各有独立、可版本化的生命周期策略，不能共享一个方便状态
字段。精确状态码、转换、跳过条件、授权和终止语义尚未批准，由
`DR-REC-010` 和 Phase 6 requirement anchor 决定。当前只冻结以下不变量：

- Requirement 状态不得伪装成设计/制造 Revision 状态；
- Revision 的释放与替代不得隐式改变物理 Set 的现场状态；
- Set 的制造、试模、生产资产和维护事实不得反写成 Revision 状态；以及
- 任何跳过或恢复都必须由精确策略版本授权并留痕。

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
- Tooling 验收前必须有有效 Revision、具体 Tooling Set、试模和重大缺陷处理结论。
- 一个 Tooling Master 可以有多个 Applicability；一个 Project Applicability 不能暗中复制 Master。
- 每个物理 Tooling Set 独立追踪，套数不能只保存为计数器。
- Trial Round 只能绑定一个具体 Tooling Master/Revision/Set 上下文和一个 Project 执行上下文。
- Trial Actual 未测量时保持 `not_measured`；复制 Customer Standard 不得伪装成测量值。
- Approved Process Baseline 只能从批准的 Trial 证据产生并保留不可变版本。
- 正式质量结果的真值来自 ERPNext；NPI 只保留引用、投影和门禁解释。
- ERPNext 正式 Item/BOM/Asset 编号只有成功 Execution Request 才能写入映射。
- 任何映射变更必须审计；同一 global_id 不得映射到多个相同类型正式对象，除非领域明确允许（例如复制模）。
- 删除优先转为作废/取消；发布、批准、执行过的对象不得物理删除。
