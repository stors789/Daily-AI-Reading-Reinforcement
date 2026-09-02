# DAIRR 项目说明

## 1. 项目简介

DAIRR（Daily AI Reading Reinforcement，日常 AI 阅读强化）是一个把 Anki 复习内容和任意文本转化为阅读、翻译与反向翻译练习的学习工作台。

项目当前同时提供三种宿主形态：

- Anki 插件：直接在 Anki 中读取卡片、复习记录和可用的 FSRS 信息。
- 独立桌面应用：以 macOS/Windows 原生窗口为主要产品方向，通过标准 AnkiConnect 与 Anki 连接；没有 Anki 时仍可使用粘贴文本练习。
- Android 应用边界：目前聚焦于无需网络的粘贴文本练习和本地会话保存。

它的核心设计是“共享学习逻辑、宿主负责平台适配”：文章生成、评分、提示词、翻译复习、解析和持久化等逻辑尽量放在平台无关的 `dairr-core` 中；Anki、桌面桥接、Android WebView 和具体数据源只通过适配器接入。

## 2. 项目要解决的问题

传统的闪卡复习通常只关注“记住答案”，DAIRR 希望进一步解决三个问题：

1. 从当天复习过的卡片中找出更值得强化的词汇，而不是随机选词。
2. 把目标词放进自然文章，让学习者在上下文中阅读和理解。
3. 让学习者用自己的语言重新表达文章，并获得针对准确性、遗漏、语法、搭配、自然度和语气等维度的 AI 反馈。

因此，DAIRR 不是单纯的文章生成器，也不是另一个闪卡复习器，而是连接“复习证据 → 目标规划 → 文章 → 翻译练习 → 反馈与历史”的完整工作流。

## 3. 主要用户流程

### 3.1 从 Anki 卡片生成文章

1. 用户在 Anki 或独立桌面应用中选择牌组。
2. DAIRR 读取卡片字段、复习信息、排程信息和历史使用情况。
3. 评分引擎为候选卡片计算强化优先级，并显示每个信号的贡献解释。
4. 用户可以预览候选、手动包含或排除卡片，并把目标标记为 Required、Preferred、Optional 或 Excluded。
5. 用户设置目标语言、难度、体裁、长度、风格和自定义指令。
6. AI 根据可见的提示词模板生成文章、标题、段落翻译和目标使用结果。
7. 文章保存到本地历史，可横向阅读或使用日文竖排阅读，也可以导出或保存为 Anki 阅读卡片。

生成流程会优先满足 Required 和 Preferred 目标，允许 Optional 目标自然省略，并对 Excluded 目标被使用的情况给出警告。词形变化、合理等价表达和结构化目标映射也会被记录。

### 3.2 使用文章进行翻译练习

用户可以打开已经保存的 DAIRR 文章，选择源语言到目标语言，或进行反向翻译。文章的段落翻译默认不直接显示，用户可按段落或全文完成自己的翻译，再选择性查看参考内容并提交 AI 复核。

每次复核会保留：

- 当前翻译草稿；
- AI 反馈；
- 可选的改进版本；
- 当前尝试与后续修订的关联；
- 文章引用和练习会话快照。

### 3.3 使用任意文本练习

在不依赖 Anki 的情况下，用户可以粘贴最多 50,000 个字符的文本，指定源语言、目标语言、翻译方向、熟练度和复核指令。文本会按段落拆分，用户可以在首次提交前编辑、拆分、合并和调整段落顺序。

练习会话可以自动保留草稿，也可以保存到本地历史，之后重新打开或删除。首次提交后，原始分段会被锁定，避免反馈与已经变化的文本错位。

## 4. 核心能力

### 4.1 强化优先级评分

评分是一个可配置的学习优先级启发式，不宣称是对卡片难度的科学测量。它可以综合以下类型的证据：

- Again、Hard、Good、Easy 等答案等级；
- 当天尝试次数、失败后恢复、重复失败；
- 最近和历史 lapse；
- 经过适配器提供的 FSRS 值；
- elapsed/overdue 时间和卡片状态；
- 重复目标、同笔记兄弟卡片和 DAIRR 最近复用情况。

用户可以使用 Recommended 预设，也可以在 Simple/Advanced 界面中调整启用状态、权重、变换、归一化、上下限和衰减。每个信号都会标记为已应用、用户禁用或数据不可用，并展示原因和来源。

重要原则是：缺失证据不会被伪装成可用的零值。比如标准 AnkiConnect 没有提供规范化 FSRS 值时，相关信号显示为 unavailable，并贡献零分。

### 4.2 目标计划与目标感知生成

评分结果会进入目标选择器。用户可以设置阈值、最大目标数、各类别数量，并覆盖自动选择结果。手动包含的卡片不会因为自动上限被静默丢弃；如果手动选择与上限冲突，界面会显示冲突。

生成结果会对每个目标给出状态，例如 exact、inflected、equivalent、used、unusable、unreported、excluded 或 excluded violation。纯文本响应没有可靠目标验证时，会明确标记为 unreported，而不是声称验证成功。

### 4.3 可见、可编辑的 AI 合约

项目为以下任务提供可编辑的系统提示词、用户模板、变量和响应合约：

- 文章生成；
- 翻译复核；
- 反向翻译复核；
- 目标验证；
- 文本分段；
- 文本预处理。

用户可以在项目、提供商或配置档案范围内覆盖模板，查看精确渲染后的请求，选择结构化或纯文本响应模式，并导入、导出或重置配置。结构化响应包含明确的输出格式要求；解析器对常见包裹文本、代码围栏、部分可恢复 JSON 和不同字段命名保持一定容错，但不会静默猜测或截断文章。

### 4.4 提供商与 reasoning 控制

DAIRR 支持 OpenAI-compatible 请求，并根据提供商能力决定可用的 reasoning/think 参数。用户可以选择：

- Disabled：不发送 reasoning/thinking 参数；
- Provider default：交给提供商默认行为；
- 显式 effort 或 budget：只有在能力声明验证通过时才显示和发送。

对未知或不确定的提供商不会猜测参数格式。真实提供商失败不会偷偷退回 mock 成功；只有用户明确选择 mock/demo 模式时才使用模拟数据。

### 4.5 阅读、历史和写回

文章支持：

- 横向阅读；
- 日文竖排阅读；
- 按段落显示翻译；
- Markdown/HTML 导出；
- 本地文章历史、筛选和只读重新打开；
- 通过对应 Anki 宿主创建并暂停阅读卡片。

文章、配置、练习会话和目标清单使用版本化、原子替换的本地持久化方式，并尽量保留未知字段，便于向后兼容。

## 5. 系统架构

```text
Anki 插件 / Tauri 桌面窗口 / Android WebView
                 │
      宿主桥接与平台适配层
                 │
       共享 dairr-core 业务逻辑
                 │
  评分 · 目标选择 · 文章生成 · 翻译复核
  提示词 · LLM 请求 · 响应解析 · 持久化
                 │
   Anki API / AnkiConnect / MoMo / AI Provider
```

### 5.1 共享核心：`packages/dairr_core/`

`dairr-core` 是平台无关的 Python 包，主要包含：

- `article_generation.py`：目标感知文章生成、结果解析和目标使用状态；
- `practice.py`、`practice_service.py`、`segmentation.py`：练习领域模型、会话、尝试、分段编辑和复核服务；
- `scoring.py`、`study_signals.py`、`target_selection.py`：学习信号、评分和目标选择；
- `prompt.py`、`prompt_templates.py`：模板注册、变量校验、范围覆盖和渲染；
- `llm.py`、`provider_requests.py`、`provider_capabilities.py`：模型请求、提供商能力和 reasoning 合约；
- `response_parsing.py`、`translation_review.py`：模型响应解析和翻译反馈；
- `atomic_persistence.py`、`practice_repository.py`、`config.py`：配置、文章/练习存储和版本兼容；
- `bridge_contract.py`、`operations.py`、`capabilities.py`：桥接协议、异步操作、取消、能力状态和安全错误。

该包不导入 Anki 的 `aqt`/`mw`、Qt、HTTP 服务、桌面窗口或 Android API。新的通用学习能力应优先放在这里；新的平台或外部服务应放在宿主适配层。

### 5.2 Anki 插件：`addon/daily_ai_reading_reinforcement/`

Anki 插件是兼容层和 Anki 专用外壳。它负责菜单入口、Qt 对话框生命周期、Anki collection/scheduler 访问、复习历史、FSRS 可选字段和 Anki 卡片写回，同时继续保留旧的 `daily_ai_reading_reinforcement.core.*` 导入路径。

插件可以利用 Anki 内部可用的更丰富证据，但共享评分公式不变。关闭牌组、切换 profile、卸载 collection 或关闭对话框时，后台操作和回调会受到生命周期保护。

### 5.3 桌面宿主：`desktop_mock/`、`desktop_app.py`、`apps/desktop/`

桌面后端是本地 loopback HTTP 服务，向共享 Web UI 提供 bridge v2。当前产品方向是 Tauri 原生窗口，Python sidecar 承载后端；浏览器启动器和 pywebview 启动器继续作为开发/回退路径。

桌面端的边界包括：

- 只通过标准 AnkiConnect 访问 Anki，不导入 Anki 内部 Python/Qt API；
- 支持 `ankiconnect`、`real_momo` 和明确选择的 `mock` 数据源；
- 配置、文章和练习数据保存在操作系统应用数据目录；
- 长操作使用操作 ID、轮询、协作取消和过期结果保护；
- bridge POST 要求 loopback Host/Origin、JSON、请求大小限制和每进程 token；
- 健康检查用于确认实例和 bridge 身份，但不假装 Anki 或 AI 提供商已经连接。

桌面默认数据目录为：

| 系统 | 默认目录 |
| --- | --- |
| macOS | `~/Library/Application Support/DAIRR/` |
| Windows | `%APPDATA%\\DAIRR\\` |
| Linux/开发环境 | `~/.local/share/dairr/` |

如果已有旧版 `~/.dairr_config.json`，项目保留其兼容读取优先级。`DESKTOP_CONFIG_PATH`、`DESKTOP_OUTPUT_DIR` 等环境变量可用于开发和测试覆盖路径。

### 5.4 Android：`apps/android/`

Android 使用本地 WebView 加载共享 HTML/CSS/JavaScript，并通过受限的 Kotlin bridge 提供平台能力。当前已实现的边界是离线粘贴文本练习：创建、分段、编辑、拆分、合并、排序、保存、列出、重新打开和删除。

Android 会把每个会话保存为应用私有目录中的 JSON 文件，并使用版本、修订号、原子写入和乐观并发检查保护数据。当前没有 Android AI provider、文章历史、Anki/AnkiDroid、FSRS、评分、提示词工作台、reasoning 或文章生成功能；这些操作会返回明确的 unavailable/unsupported 结果，不会返回伪造成功。

## 6. 数据、隐私与安全边界

- 配置、文章历史和练习历史默认保存在本地。
- 只有用户提交 AI 操作时，文本才会发送到用户配置的模型端点。
- API key、私有文本、翻译、提示词、原始模型响应和原始 provider body 不应进入普通诊断、健康响应或公开 bridge 错误。
- 桌面 bridge 只监听 loopback，并校验 Host/Origin、进程 token、内容类型和请求体大小。
- 服务响应使用 no-store、CSP、禁止 frame 等安全响应头。
- 配置和内容写入采用同目录临时文件、刷新和原子替换；支持的平台上使用私有文件权限。
- Android 禁止外部导航、混合内容以及不受信任的 file/content 访问，Activity 销毁时关闭 dispatcher、移除 JavaScript interface 并销毁 WebView。
- Android 当前凭据存储保持 fail-closed；在没有 Keystore 支持和正式移动 provider 之前，不接受明文 provider secret。

## 7. 当前平台能力对比

| 能力 | Anki 插件 | 独立桌面 | Android 当前版本 |
| --- | --- | --- | --- |
| 粘贴文本练习 | 支持 | 支持，不需要 Anki | 支持离线本地练习 |
| 保存文章练习 | 支持 | 支持本地文章历史 | 暂不支持 |
| Anki 数据 | 原生 Anki API | 标准 AnkiConnect | 暂不支持 |
| 当天有序复习证据 | 支持，取决于 Anki 数据 | 仅在证据和当天边界可靠时支持 | 暂不支持 |
| FSRS | 有可用字段时支持 | 标准 AnkiConnect 通常不可用 | 暂不支持 |
| 评分与目标计划 | 支持 | 支持 | 暂不支持 |
| AI 文章生成与翻译复核 | 支持 | 支持 | 暂不支持 |
| 保存为 Anki 阅读卡片 | 支持 | AnkiConnect 连接并配置时支持 | 暂不支持 |
| 本地历史 | 文章和练习 | 文章和练习 | 仅粘贴练习 |

## 8. 代码和文档入口

- `README.md`：安装、快速开始、能力摘要和常用命令。
- `packages/dairr_core/`：共享平台无关核心。
- `addon/daily_ai_reading_reinforcement/`：Anki 插件和共享 Web UI。
- `desktop_mock/`：桌面后端、bridge、数据源、诊断和 AnkiConnect/MoMo 适配器。
- `apps/desktop/`：Tauri 桌面壳和 sidecar 配置。
- `apps/android/`：Android WebView、bridge 和离线练习存储。
- `docs/architecture/`：架构决策记录和边界说明。
- `docs/user-guide.md`：面向用户的完整使用指南。
- `docs/desktop_standalone.md`：桌面 provider、bridge、路径和诊断说明。
- `docs/packaging.md`：Anki、桌面 sidecar、Tauri 和回退包的构建说明。
- `docs/manual-verification.md`：发布前人工验收清单。

## 9. 开发、测试与打包

建议使用 Python 3.11 或更高版本。常用检查包括：

```bash
python3 -m unittest discover -s tests
python3 -m compileall .
python3 package_addon.py
python3 package_desktop.py --entry browser --dry-run
python3 package_desktop.py --entry native --dry-run
python3 package_tauri_sidecar.py --dry-run
python3 apps/android/tests/validate_scaffold.py
python3 scripts/desktop_release.py pre-publish
```

其中 `pre-publish` 是无凭据的综合发布门禁，覆盖 Python 编译和导入、单元测试、插件隐私检查、Web UI/JavaScript 检查、Android 静态验证、桌面打包 dry-run 和 Rust 编译。它不能替代目标操作系统上的实际构建、安装、签名、公证、更新和带真实凭据的 provider 验证。

Anki 插件包通过以下命令生成：

```bash
python3 package_addon.py
```

Tauri 桌面包需要先在目标操作系统和架构上构建 Python sidecar，再构建 Tauri bundle。macOS DMG、Windows NSIS、代码签名、公证、WebView2、AnkiConnect、MoMo 和 Android 真机行为都必须在对应环境单独验证。

## 10. 当前状态与剩余风险

当前仓库已经实现了共享核心、Anki 插件、桌面独立模式的主要工作流，以及 Android 离线粘贴练习边界。项目文档和自动化检查较完整，但以下事项不能仅凭源码或 dry-run 视为已完成：

- 面向用户发布的 macOS/Windows 签名安装包和更新链路；
- Windows 安装、WebView2、卸载和 SmartScreen 验证；
- macOS 各架构的签名、公证、stapling 和安装验证；
- 真实 Anki/AnkiConnect、MoMo 和 AI provider 凭据下的最终 smoke test；
- Android 正式 APK、Android SDK 构建、真机/模拟器验收；
- Android AI provider、AnkiDroid 同步或写回、文章历史和评分能力。

因此，DAIRR 当前更准确的定位是：核心学习产品和跨宿主架构已经落地，桌面发行与 Android 完整能力仍处于需要目标环境验证和逐步扩展的阶段。
