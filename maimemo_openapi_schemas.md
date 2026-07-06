# 墨墨开放 API Schema 调研报告 (Daily AI Reading Reinforcement)

针对 [墨墨开放 API](https://open.maimemo.com/#) 的接口及数据结构，基于本项目（Anki 与墨墨背单词的联动/AI 辅助阅读强化）的核心需求，我们对可供项目使用的 Schema 进行了梳理与分类。

## 1. 核心可用 Schema（对本项目极具价值）

这些 Schema 直接对应于我们在阅读强化、生词本管理、发音与释义查询、学习进度同步等方面的核心业务场景。

### 1.1 单词查询与定义 (Vocabulary & Interpretation)
我们的核心功能需要在阅读时提取生词、查询单词发音及释义。
- **Vocabulary (单词)**: 核心实体。提供单词的拼写、音标、发音音频等基础信息。可用于 Anki 卡片正面的基础内容。
- **Interpretation (释义)**: 单词释义。可用于获取墨墨中该单词的中文或英文释义。
- **InterpretationStatus (释义状态)**: 释义状态（发布、未发布、删除）。

*(对应的关键接口：`GET/POST /api/v1/vocabulary/query`, `GET/POST /api/v1/interpretations`)*

### 1.2 例句资源 (Phrase)
在阅读强化中，基于上下文的例句极其重要，能够丰富 Anki 卡片的背面。
- **Phrase (例句)**: 包含例句文本及翻译，直接可用于 AI 强化语境的构建。
- **PhraseHighlightRange (例句中的单词高亮区间)**: 用于精准标出当前目标生词在例句中的位置，方便前端或 Anki 卡片模板中高亮展示。
- **PhraseStatus (例句状态)**: （发布、删除）。

*(对应的关键接口：`GET/POST /api/v1/phrases`)*

### 1.3 学习数据与同步 (Study Data)
本项目在 Phase 中曾深度对接了墨墨的学习记录 (`study_records`)，用于判断用户对某些单词的熟悉度，从而决定是否需要生成 Anki 卡片。
- **StudyRecord (学习记录)**: 包含历史复习次数、上次复习结果等，是我们判断单词掌握程度的核心依据。
- **StudyTodayItem (今日学习单词)**: 获取今日正在复习或新学的单词。
- **StudyProgress (学习进度)**: 整体进度。
- **StudyResponse (学习反馈)**: 表示对单词的掌握情况 (`FAMILIAR`: 认识, `VAGUE`: 模糊, `FORGET`: 忘记, `WELL_FAMILIAR`: 熟知, `CANCEL_WELL_FAMILIAR`: 取消熟知)。对双向同步有价值。

*(对应的关键接口：`POST /api/v1/study/query_study_records`, `POST /api/v1/study/get_today_items`, `POST /api/v1/study/add_words`)*

### 1.4 云词本 (Notepad)
用户在阅读中划词后，除了导入 Anki，还可能需要一键存入“墨墨云词本”，以便在墨墨 App 中复习。
- **Notepad (云词本)**: 代表云词本实体。
- **BriefNotepad (简要云词本)**: 云词本概览数据。
- **NotepadParsedItem (云词本解析结果)**: 往云词本中批量添加单词时的解析模型。
- **NotepadStatus (云词本状态)**, **NotepadType (云词本类型)**: 如 `FAVORITE` (我的收藏), `NOTEPAD` (云词本)。

*(对应的关键接口：`GET/POST /api/v1/notepads`)*

### 1.5 助记 (Note)
如果在 Anki 端生成的 AI 助记/联想故事需要同步到墨墨，就可以使用此类 Schema。
- **Note (助记)**: 表示具体的助记内容，可结合 AI 生成的故事写入。
- **NoteStatus (助记状态)**: （发布、删除）。

*(对应的关键接口：`GET/POST /api/v1/notes`)*

---

## 2. 次要 / 暂不需要的 Schema（简要记录）

墨墨除了背单词 App 外，还提供了“墨墨记忆卡”（Markji），其逻辑与 Anki 高度重合（都是 Flashcard 类）。因为本项目本质上是 **Anki Addon**，主要依托 Anki 生态进行制卡与排程，所以针对 Markji (墨墨记忆卡) 的增删改查 Schema 在当前产品定位下暂无直接用处，仅做简要记录以备后续（如需支持双卡片平台一键导出）之用。

- **MarkjiDeck (牌组)** & **MarkjiRootDeck (根牌组)**: 记忆卡牌组。
- **MarkjiCard (记忆卡片)**: 卡片实体。
- **MarkjiChapterset (章节集合)** & **MarkjiChapter (章节)**: 牌组下的分类组织结构。
- **MarkjiFolder (文件夹)**, **MarkjiFolderItem (文件夹对象)**, **MarkjiFolderItemClass (类型:文件夹/牌组)**: 卡片库的归类层级。
- **MarkjiFile (文件)**: 用于存储卡片里的富文本附件/图片/音频。
- **MarkjiSource (来源)**: 牌组的来源（`SELF`: 自建, `FORK`: 派生）。
- **MarkjiStatus (状态)**: `NORMAL`, `DELETED`, `BLOCKED`。
- **MarkjiContentType (内容类型)**: 如 `PLAIN` 纯文本等。

*(对应的关键接口：`GET/POST /api/v1/markji/*`)*
