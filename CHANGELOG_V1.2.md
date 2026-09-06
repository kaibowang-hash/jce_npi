# V1.2 修订说明：工业界面与翻译硬约束

本版本纠正 V1.1 中两项表述不足：

1. **UI 基线不再写成泛化的“混合企业风格”**。Siemens Industrial Experience（iX）Classic Light 与经典西门子工程软件的布局逻辑成为唯一主要基线；普通业务界面必须单一主色、灰白中性色、0–2px 普通圆角、平面边界、紧凑树表、稳定分栏与停靠式检查器。
2. **本地化不再写成“中文优先并支持 i18n”**。英文是唯一源语言；Python、Frappe JavaScript 和 React 分别通过 `_()`、`__()`、本地 `t()` 进入同一 Frappe 翻译事实源。简体中文与繁体中文必须完整翻译，除受控缩写、产品名、业务数据、编码和单位外，普通语言混用直接阻断发布。

同步新增或强化：
- `design/UI_VISUAL_BASELINE.md` 与 `design/design-tokens.json`；
- `docs/LOCALIZATION_SPEC.md`；
- `contracts/terminology-allowlist.yaml`；
- `frappe-i18n` 与 `industrial-ux` Codex skills；
- 三语言翻译种子文件；
- UI、语言和发布门禁验收；
- UI/本地化专项评审 Prompt；
- 克制、方正的中文 UI 基准图。
