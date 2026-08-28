# 实施路线图

## 总体原则

不是先建完数据表再补 UI，也不是先把所有 DocType 暴露出来。采用“先体验原型、再领域底座、再最小纵切”的交付方式。每个里程碑必须能演示一条真实业务路径并通过对应 release gate。

## M0 — 发现与决策（只分析，不开发业务功能）

### 目标
把业务目标与真实仓库、现有 ERPNext 自定义模块、团队能力和部署约束对齐。

### 必交付
- 仓库地图、运行/测试/CI 方式；
- ERPNext 版本、现有自定义 App/DocType/Hooks/API/权限/文件策略盘点；
- `docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md` 中每个相关项具有明确的
  Required / Optional / Already Present / Not Required / Blocked Pending Fact
  分类、证据状态与责任人；未知项不得猜测；
- 当前数据主责和痛点；
- 上下文/容器/数据流图；
- ADR-001~010 草案，包括 Siemens 式视觉基线、组件适配、Frappe 翻译格式与 React 翻译适配；
- 风险、未知项和决策清单；
- M1 任务拆分与估算相对等级；
- 脱敏样例数据方案；
- 不改代码的演示/设计环境计划。

### 禁止
创建完整脚手架、数据库迁移、安装生产依赖、改核心、实现业务功能。

## M1 — 统一体验与高保真原型

### 目标
验证产品是否真正统一、好用，不让技术结构决定用户流程。

### 建议任务
- M1-01 Siemens iX Classic Light 组件基线、经典工程布局和 design token；
- M1-02 Frappe i18n 基线、英文源、简体/繁体中文 catalog、术语白名单和自动检查；
- M1-03 App Shell、矩形导航、全局搜索、环境标识和状态栏；
- M1-04 “我的工作”工程工作清单；
- M1-05 项目驾驶舱（工程对象页）；
- M1-06 阶段门评审室；
- M1-07 模具开发驾驶舱；
- M1-08 试模工作区；
- M1-09 ERPNext 执行面板；
- M1-10 6 条三语言可点击黄金路径与可用性测试；
- M1-11 修复严重问题并冻结视觉、交互和翻译基线。

### Exit
三类业务代表完成任务；无未关闭严重可用性问题；视觉和 i18n ADR 获批；英文、简体中文、繁体中文均无普通语言混用；后端 ViewModel/API 需求被记录。

## M2 — 领域、安全与 API 底座

- 独立 Frappe Site/App 最小骨架；
- 身份/SSO 与服务身份；
- 项目级权限和外部用户隔离；
- 审计、global_id、乐观并发；
- 领域 API v1、统一错误和 trace；
- 文件版本/哈希/扫描接口；
- 基础 Outbox/Inbox；
- 前端真实壳连接 mock/contract server，再连接领域 API。

Exit：安全、API 和迁移基线通过；没有业务用户依赖 Desk。

## M3 — 项目、工作项与 Gate 纵切

最小演示：
创建客户来模项目 → 模板生成 G0/G1 → 分配团队/行动 → 上传证据 → 阶段门评审 → 决策快照 → 我的工作更新。

范围：项目、团队、RACI、WorkItem、Gate、Evidence、评论/活动。
非范围：复杂资源计划、正式 ERP 发布。

## R1 — V1.2 reconciliation 与共享体验桥接

在 P5-01 后端 checkpoint 后、继续产品代码前完成：

1. DOCX–Pack additive addendum、229 行原需求、coverage matrix、R1-01
   的 281 行追踪加 FR-UX-043 追加修正后共 282 行带 trace kind 的机器追踪，
   以及 43 列 Tooling mapping；
2. 只使用 `docs/Brand Asset/` CSV/资产的 LaunchFlow display adapter；
3. 可折叠域导航、上下文 quick-create/command foundation；
4. 可拖动/持久化列宽、个人/共享视图和受控 export foundation；
5. 边界拖动分栏、字段可编辑性、附件状态和本地 icon-first 动作 primitives；
6. 低风险限时撤销契约、模块 prototype gate，以及在既有尺寸之外新增
   1440×900 三语言 P0 视觉矩阵；
7. My Work inline expansion 仅在 DR-REC-001 批准后执行。

R1-01 是 documentation/trace only。其后共享 Shell/design/i18n 变更触发
Level 3 bridge gate；通过后才恢复未完成的 P5-01。

## M4 — 设计、文档、基线与 EBOM

最小演示：
客户输入 → 设计修订 → 评审 → 发布 Baseline → Gate 引用 → 新修订触发影响 → EBOM 草稿/差异。

正式 Item/MBOM 创建先用 Execution Request 契约和 sandbox stub，M7 接 ERPNext。

增加受控打印 foundation：SPA/BFF 调用服务端 Frappe Print Format registry，
从不可变快照输出带版本/hash/语言/审计的受控 PDF。具体表单、签字、浏览器
打印和 copy numbering 等待 DR-REC-003/004。

## M5 — Tooling

分五个纵切：
1. Tooling Requirement/Master/Applicability/Revision/physical Set；
2. 客户来模接收/差异/授权及逐套追踪；
3. 穴位/封穴/镶件/双色包胶、受控规格、过程基线和 Capacity Scenario；
4. 新制模具设计/制造/供应商/成本投影、缺陷及验收/资产请求；
5. 43 列客户 Tooling List 专用导入和 selection/filter/object-package 导出。

专用导入执行上传、识别、映射、转换、校验、预览、异步执行、
审计/回滚八步，保留原文件/批次/行/原值/转换/确认 provenance，
并使用 `xlsx-tooling-import` Skill。未批准的列语义和 downstream rollback
cutoff 保持 scoped hold。

Exit：模具开发驾驶舱覆盖完整生命周期，设计释放和重大缺陷规则有效。

## M6 — Trial 与 NPI

- Trial Plan/Round；
- 输入版本锁和继承；
- 参数/材料/样件/穴号；
- 缺陷/行动/根因；
- 轮次比较与结论；
- 质量引用；
- NPI 清单/阻断/评分；
- G6/G7 移交和观察期。
- 不可变 Released Trial Summary、一页式 Trial output 和只读投影契约输入。
- 手机现场审批、状态更新、拍照上传、问题记录和扫码；复杂表格仍在桌面。

Exit：AT-01/02 的 NPI 侧黄金路径通过。

## M7 — ERPNext 可靠集成

按风险从只读到写入：
1. 客户/供应商/Item/PO/质量/资产只读同步；
2. Webhook 签名、Inbox 和投影；
3. Item 正式发布；
4. MBOM 发布；
5. Tool Asset 移交；
6. 质量请求/结果；
7. DLQ、回放、对账和运维页面。
8. NPI 侧 Released Trial Summary 只读 projection contract 与 sandbox-ready
   adapter；正式目标显示身份等待批准资产，禁止生产连接。

每种写操作独立幂等和契约测试。不得用一个“通用写 DocType API”绕过业务规则。
任何 Sandbox 或生产集成激活前，必须逐项闭合 ERPNext 定制需求矩阵中的精确
方法、字段、权限、迁移、测试、上线与回滚事实；缺失事实保持 unavailable/held。

## M8 — 变更、组合与外部协作

- ERP 正式变更引用；
- 影响对象图和任务包；
- Gate/Trial 复审；
- 组合健康度/KPI；
- 内部供应商里程碑/观察与客户批准证据/版本锁继续属于 V1.2；
- 供应商/客户外部登录、身份、自助提交、批准 UI/API 以
  `USER_APPROVED_POST_V1_2_DEFERRED` 决策标记移至未来版本，原
  `FR-CO-003`/`FR-CO-004` 与 `M8-03`/`M8-04` 保留；
- 通知升级和受控分享。

外部门户恢复必须作为独立未来版本入口，在外部身份拓扑、租户/项目授权、
文件与证据政策、客户批准权限、通知/隐私/安全威胁模型、回滚和发布门获得批准
后才能激活。该延期不删除需求，也不把内部供应商/客户协作证据标为延期。

## M9 — 加固、迁移与试点

- 性能、安全、灾备、备份恢复；
- 历史数据映射与预演；
- 通用 Data Exchange、enterprise export、correction artifact 和 print coverage 加固；
- 操作/支持手册；
- 一个客户来模 + 一个新制模具真实试点；
- 两个项目跑完 Gate/Trial/ERP 移交；
- 指标与可用性复测；
- 在完整产品和两类试点上量化 Project Workspace 80% 日常工作目标；
- 分批上线和回滚演练。
- ERPNext 定制需求矩阵、外部事实 provenance/checksum、Sandbox/UAT、监控支持、
  回滚/forward-fix 与明确 no-change 清单通过最终 Release Gate；生产只读核对仍需
  单独更高优先级规则修订和 Gate，不能由文档基线自动授权。

## 任务粒度

理想任务：
- 1 个主用户故事；
- 1 个领域纵切；
- 1–5 天可完成；
- 变更范围可评审；
- 验收可自动或明确人工复现；
- 独立回滚；
- 不要求并行修改大量无关模块。

过大的任务必须先拆分，过小的纯技术任务应与用户价值纵切绑定。
