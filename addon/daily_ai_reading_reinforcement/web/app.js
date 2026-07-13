(function () {
  const HISTORY_ALL_DECKS = "__dairr_all_decks__";

  const state = {
    selectedDeckId: null,
    decks: [],
    sources: [],
    selectedSourceId: null,
    collapsedDeckGroups: new Set(),
    fields: [],
    selectedFields: [],
    currentCards: [],
    selectedCardIds: new Set(),
    promptPresets: [],
    selectedPromptPresetId: "default",
    uiLanguage: "zh",
    providerProfiles: [],
    modelOptions: [],
    autoSelectedDeck: false,
    apiSettings: {
      providerId: "openai",
      baseUrl: "https://api.openai.com/v1",
      model: "gpt-4.1-mini",
      temperature: 0.7,
      maxTokens: 30000,
      hasApiKey: false,
    },
    articleCardSettings: {
      parentDeck: "Daily AI Reading Reinforcement",
      noteType: "Daily AI Reading Reinforcement Article",
    },
    desktopSettings: {
      hasMomoApiKey: false,
      momoDayStart: "04:00",
      momoDayEnd: "04:00",
    },
    statusData: { key: "selectDeck", isError: false, params: {} },
   readingMode: false,
   writingMode: "horizontal",
   readingTab: "article",
    historyArticles: [],
    historySelectedDeck: null,
   historySelectedDate: null,
   readingHistoricalArticle: false,
   currentArticlePath: "",
   currentArticleDay: "",
   dayStart: 0,
    dayEnd: 0,
  };

  const el = {
    eyebrowText: document.getElementById("eyebrowText"),
    titleText: document.getElementById("titleText"),
    uiLanguageSelect: document.getElementById("uiLanguageSelect"),
    deckList: document.getElementById("deckList"),
    sourceList: document.getElementById("sourceList"),
    cardList: document.getElementById("cardList"),
    cardCount: document.getElementById("cardCount"),
    selectFailedCardsButton: document.getElementById("selectFailedCardsButton"),
    selectAllCardsButton: document.getElementById("selectAllCardsButton"),
    selectNewCardsButton: document.getElementById("selectNewCardsButton"),
    selectVagueCardsButton: document.getElementById("selectVagueCardsButton"),
    clearCardSelectionButton: document.getElementById("clearCardSelectionButton"),
    dayWindow: document.getElementById("dayWindow"),
    sourcesHeading: document.getElementById("sourcesHeading"),
    decksHeading: document.getElementById("decksHeading"),
    fieldsHeading: document.getElementById("fieldsHeading"),
    cardsHeading: document.getElementById("cardsHeading"),
    articleHeading: document.getElementById("articleHeading"),
    settingsHeading: document.getElementById("settingsHeading"),
    generateButton: document.getElementById("generateButton"),
    regenerateButton: document.getElementById("regenerateButton"),
    saveArticleToCardButton: document.getElementById("saveArticleToCardButton"),
    selectAllFieldsButton: document.getElementById("selectAllFieldsButton"),
    invertFieldsButton: document.getElementById("invertFieldsButton"),
    saveFieldsButton: document.getElementById("saveFieldsButton"),
    refreshButton: document.getElementById("refreshButton"),
    providerOffline: document.getElementById("providerOffline"),
    providerOfflineMessage: document.getElementById("providerOfflineMessage"),
    providerRetryButton: document.getElementById("providerRetryButton"),
    fieldList: document.getElementById("fieldList"),
    presetSelect: document.getElementById("presetSelect"),
    presetName: document.getElementById("presetName"),
    presetReaderNativeLanguage: document.getElementById("presetReaderNativeLanguage"),
    presetArticleLanguage: document.getElementById("presetArticleLanguage"),
    returnToSelectionButton: document.getElementById("returnToSelectionButton"),
    presetDifficulty: document.getElementById("presetDifficulty"),
    presetMaxWords: document.getElementById("presetMaxWords"),
    presetInstructions: document.getElementById("presetInstructions"),
    newPresetButton: document.getElementById("newPresetButton"),
    savePresetButton: document.getElementById("savePresetButton"),
    deletePresetButton: document.getElementById("deletePresetButton"),
    providerSelect: document.getElementById("providerSelect"),
    apiProfileSelect: document.getElementById("apiProfileSelect"),
    apiProfileNameInput: document.getElementById("apiProfileNameInput"),
    fetchModelsButton: document.getElementById("fetchModelsButton"),
    modelSelect: document.getElementById("modelSelect"),
    providerLabel: document.getElementById("providerLabel"),
    baseUrlLabel: document.getElementById("baseUrlLabel"),
    modelLabel: document.getElementById("modelLabel"),
    apiKeyLabel: document.getElementById("apiKeyLabel"),
    temperatureLabel: document.getElementById("temperatureLabel"),
    maxTokensLabel: document.getElementById("maxTokensLabel"),
    clearApiKeyLabel: document.getElementById("clearApiKeyLabel"),
    articleCardDeckHint: document.getElementById("articleCardDeckHint"),
    baseUrlInput: document.getElementById("baseUrlInput"),
    modelInput: document.getElementById("modelInput"),
    apiKeyInput: document.getElementById("apiKeyInput"),
    temperatureInput: document.getElementById("temperatureInput"),
    maxTokensInput: document.getElementById("maxTokensInput"),
    clearApiKeyInput: document.getElementById("clearApiKeyInput"),
    apiKeyStatus: document.getElementById("apiKeyStatus"),
    saveApiSettingsButton: document.getElementById("saveApiSettingsButton"),
    testApiSettingsButton: document.getElementById("testApiSettingsButton"),
    status: document.getElementById("status"),
    articleOutput: document.getElementById("articleOutput"),
    articleScroll: document.getElementById("articleScroll"),
    readingHeader: document.getElementById("readingHeader"),
    notesPanel: document.getElementById("notesPanel"),
    readingTabs: document.getElementById("readingTabs"),
    readingTabArticle: document.getElementById("readingTabArticle"),
    readingTabNotes: document.getElementById("readingTabNotes"),
    savedPaths: document.getElementById("savedPaths"),
    historyButton: document.getElementById("historyButton"),
   historyPanel: document.getElementById("historyPanel"),
   historyHeading: document.getElementById("historyHeading"),
    historyDecks: document.getElementById("historyDecks"),
    historyRight: document.getElementById("historyRight"),
    historyHeatmap: document.getElementById("historyHeatmap"),
    historyArticles: document.getElementById("historyArticles"),
   historyCloseButton: document.getElementById("historyCloseButton"),
    historyEmptyText: document.getElementById("historyEmptyText"),
    deleteDayArticlesButton: document.getElementById("deleteDayArticlesButton"),
    deleteCurrentArticleButton: document.getElementById("deleteCurrentArticleButton"),
    desktopSettingsButton: document.getElementById("desktopSettingsButton"),
    desktopSettingsPanel: document.getElementById("desktopSettingsPanel"),
    desktopSettingsHeading: document.getElementById("desktopSettingsHeading"),
    desktopSettingsCloseButton: document.getElementById("desktopSettingsCloseButton"),
    momoApiKeyLabel: document.getElementById("momoApiKeyLabel"),
    momoApiKeyInput: document.getElementById("momoApiKeyInput"),
    momoApiKeyStatus: document.getElementById("momoApiKeyStatus"),
    clearMomoApiKeyInput: document.getElementById("clearMomoApiKeyInput"),
    clearMomoApiKeyLabel: document.getElementById("clearMomoApiKeyLabel"),
    momoDayStartLabel: document.getElementById("momoDayStartLabel"),
    momoDayStartInput: document.getElementById("momoDayStartInput"),
    momoDayEndLabel: document.getElementById("momoDayEndLabel"),
    momoDayEndInput: document.getElementById("momoDayEndInput"),
    saveDesktopSettingsButton: document.getElementById("saveDesktopSettingsButton"),
    writingModeButtons: document.getElementById("writingModeButtons"),
    writingModeHorizontal: document.getElementById("writingModeHorizontal"),
    writingModeVertical: document.getElementById("writingModeVertical"),
  };

  const I18N = {
    zh: {
      group_light: "🌞 浅色与清新",
      group_retro: "☕ 护眼与复古",
      group_dark: "🌑 深邃与极简",
      group_neon: "⚡ 赛博与霓虹",

      theme_macchiato: "焦糖玛奇朵",
      theme_rosegold: "玫瑰柔金",
      theme_forest: "迷雾森林",
      theme_sunset: "沙丘蜃景",
      theme_glacier: "极地冰川",
      theme_neontokyo: "霓虹东京",
      theme_lunarslate: "月岩暗面",
      theme_midnightjazz: "午夜爵士",
      theme_retromac: "老式麦金塔",
      theme_abyss: "深渊代码",
      theme_cyberpunk: "赛博朋克 2077",

      theme_light: "明亮",
      theme_dark: "暗色",
      theme_oled: "OLED 空境",
      theme_dracula: "德古拉",
      theme_cyberviolet: "赛博紫",
      theme_lavender: "暮色薰衣草",
      theme_gruvbox: "复古暖夜",
      theme_nord: "北欧极光",
      theme_matcha: "抹茶",
      theme_amethyst: "紫水晶",
      theme_eink: "墨水屏",
      theme_sepia: "羊皮纸",
      theme_oceanic: "深海",
      theme_sakura: "樱花",
      theme_glass: "毛玻璃拟态",
      theme_outrun: "迈阿密波浪",

      eyebrow: "每日 AI 阅读",
      title: "阅读巩固",
      sources: "学习来源",
      decks: "今日卡组",
      fields: "AI 字段",
      cards: "卡片",
      article: "文章",
      settings: "API 设置",
      refresh: "刷新",
      retry: "重试",
      ankiConnectOffline: "无法连接 AnkiConnect。请启动 Anki，并确认 AnkiConnect 已安装和启用。",
      all: "全选",
      invert: "反选",
      save: "保存",
      generate: "生成",
      new: "新建",
      delete: "删除",
      generating: "生成中...",
      returnToSelection: "退出阅读模式",
      loadingDay: "正在读取 Anki 日期...",
      selectDeck: "选择一个今天学过的卡组。",
      noStudy: "这个 Anki 日没有找到学习记录。",
      noDecks: "这个 Anki 日没有学习过的卡组。",
      loadingCards: "正在读取卡片...",
      ready: "可以生成了。",
      noCards: "这个卡组今天没有候选卡片。",
      noFields: "没有可用字段。",
      chooseField: "请至少选择一个 AI 输入字段。",
      chooseCard: "请至少选择一张卡片。",
      fieldSaved: "字段选择已保存。",
      presetSaved: "提示词预设已保存。",
      presetUpdated: "提示词预设已更新。",
      savedArticle: "文章已保存：",
      markdownPath: "Markdown",
      htmlPath: "HTML",
      sourceDeck: "来源卡组",
      generatedAt: "生成时间",
      reviewNotes: "复习笔记",
      reviewNotesEmpty: "暂无复习笔记。",
      readingTabArticle: "文章",
      readingTabNotes: "笔记",
      sourceTerms: "来源词条",
      fallbackTitle: "阅读文章",
      selectDeckShort: "请选择卡组",
      candidateCards: "张候选卡",
      selectedCards: "已选",
      selectNewCards: "新学",
      selectFailedCards: "遗忘",
      selectVagueCards: "模糊",
      clearCardSelection: "清空",
      cardsUnit: "张卡",
      newCount: "新学",
      failedCount: "失败",
      vagueCount: "模糊",
      reviews: "次复习",
      childDecks: "个子卡组",
      expandCollapse: "展开或折叠",
      presetName: "预设名称",
      readerNativeLanguage: "阅读者母语",
      articleLanguage: "生成文章语言",
      difficulty: "难度",
      maxWords: "字数范围",
      instructions: "格式要求",
      provider: "服务商",
      baseUrl: "Base URL",
      model: "模型",
      apiKey: "API key",
      temperature: "温度",
      maxTokens: "最大 tokens",
      fetchModels: "获取模型",
      chooseModel: "选择模型",
      fetchingModels: "正在获取模型...",
      modelsFetched: "模型列表已更新。",
      clearApiKey: "清除已保存 key",
      regenerate: "重生成",
      saveArticleToCard: "保存到卡片",
      articleCardDestination: "文章卡片牌组：",
      articleCardSkipped: "未创建文章卡片",
      saveApiSettings: "保存 API 设置",
      keySaved: "Key 已保存",
      noKey: "无 key",
      enterNewKey: "留空则保留已保存 key",
      apiSettingsSaved: "API 设置已保存。",
      testApiSettings: "测试当前配置",
      testingApiSettings: "正在测试当前配置...",
      apiSettingsTested: "配置可用，模型连接成功。",
      articleCardSettingSaved: "文章卡片设置已保存。",
      articleCardSaved: "文章卡片已创建到",
      articleCardFailed: "文章已保存，但创建卡片失败：",
      apiMissingBaseUrl: "请输入 API Base URL。",
      apiMissingModel: "请输入模型名称。",
      toggleTranslation: "显示/隐藏翻译",
      translateButtonShort: "译",
      historyTitle: "历史文章",
      historyEmpty: "没有已保存的文章。",
      historyCards: "张卡片",
     historyClose: "关闭",
      historyDecksHeading: "牌组",
      historyHeatmapHeading: "日期",
      historyArticlesHeading: "文章",
      historyNoDeck: "请选择一个牌组。",
      historyNoDate: "请选择一个日期。",
      historyArticlesCount: "篇文章",
      historyRecentDate: "最近",
      historyAllDecks: "全部牌组",
      deleteArticle: "删除文章",
      deleteSelectedDay: "清空所选日期",
      deleteDayPrefix: "清空",
      confirmDelete: "再次点击确认",
      desktopSettingsTitle: "设置",
      momoApiKey: "墨墨 API",
      clearMomoApiKey: "清除已保存的墨墨 API",
      momoDayStart: "一天开始",
      momoDayEnd: "一天结束",
      saveDesktopSettings: "保存设置",
      desktopSettingsSaved: "设置已保存。",
      momoKeySaved: "墨墨 API 已保存",
      momoNoKey: "未保存墨墨 API",
      enterNewMomoKey: "留空则保留已保存墨墨 API",
     writingHorizontal: "横",
     writingVertical: "竖",
   },
   en: {
      group_light: "🌞 Light & Bright",
      group_retro: "☕ Warm & Retro",
      group_dark: "🌑 Dark & Minimal",
      group_neon: "⚡ Cyberpunk & Neon",

      theme_macchiato: "Macchiato",
      theme_rosegold: "Rose Gold",
      theme_forest: "Forest Canopy",
      theme_sunset: "Sunset Mirage",
      theme_glacier: "Glacier",
      theme_neontokyo: "Neon Tokyo",
      theme_lunarslate: "Lunar Slate",
      theme_midnightjazz: "Midnight Jazz",
      theme_retromac: "Retro Mac 1984",
      theme_abyss: "Abyss",
      theme_cyberpunk: "Cyberpunk 2077",

      theme_light: "Light",
      theme_dark: "Dark",
      theme_oled: "OLED Void",
      theme_dracula: "Dracula",
      theme_cyberviolet: "Cyber Violet",
      theme_lavender: "Lavender Twilight",
      theme_gruvbox: "Gruvbox Retro",
      theme_nord: "Nord",
      theme_matcha: "Matcha",
      theme_amethyst: "Amethyst",
      theme_eink: "E-Ink Paper",
      theme_sepia: "Sepia Antique",
      theme_oceanic: "Oceanic",
      theme_sakura: "Sakura Spring",
      theme_glass: "Glassmorphism",
      theme_outrun: "Outrun",

      eyebrow: "Daily AI Reading",
      title: "Reading Reinforcement",
      sources: "Learning sources",
      decks: "Studied Decks",
      fields: "AI Fields",
      cards: "Cards",
      article: "Article",
      settings: "API Settings",
      refresh: "Refresh",
      retry: "Retry",
      ankiConnectOffline: "Cannot connect to AnkiConnect. Start Anki and confirm that AnkiConnect is installed and enabled.",
      all: "All",
      invert: "Invert",
      save: "Save",
      generate: "Generate",
      new: "New",
      delete: "Delete",
      generating: "Generating...",
      returnToSelection: "Return to selection",
      loadingDay: "Loading Anki day...",
      selectDeck: "Choose a deck studied today.",
      noStudy: "No study activity found for this Anki day.",
      noDecks: "No decks studied in this Anki day.",
      loadingCards: "Loading cards...",
      ready: "Ready to generate.",
      noCards: "No candidate cards in this deck today.",
      noFields: "No fields found.",
      chooseField: "Choose at least one field for AI input.",
      chooseCard: "Choose at least one card.",
      fieldSaved: "Field selection saved.",
      presetSaved: "Prompt preset saved.",
      presetUpdated: "Prompt presets updated.",
      savedArticle: "Saved article for ",
      markdownPath: "Markdown",
      htmlPath: "HTML",
      sourceDeck: "Source deck",
      generatedAt: "Generated",
      reviewNotes: "Review notes",
      reviewNotesEmpty: "No review notes yet.",
      readingTabArticle: "Article",
      readingTabNotes: "Notes",
      sourceTerms: "Source terms",
      fallbackTitle: "Reading Article",
      selectDeckShort: "Choose a deck",
      candidateCards: "candidate cards",
      selectedCards: "selected",
      selectNewCards: "New",
      selectFailedCards: "Forgotten",
      selectVagueCards: "Vague",
      clearCardSelection: "Clear",
      cardsUnit: "cards",
      newCount: "new",
      failedCount: "failed",
      vagueCount: "vague",
      reviews: "reviews",
      childDecks: "child decks",
      expandCollapse: "Expand or collapse",
      presetName: "Preset name",
      readerNativeLanguage: "Reader Native Language",
      articleLanguage: "Article Language",
      difficulty: "Difficulty",
      maxWords: "Word range",
      instructions: "Formatting requirements",
      provider: "Provider",
      baseUrl: "Base URL",
      model: "Model",
      apiKey: "API key",
      temperature: "Temperature",
      maxTokens: "Max tokens",
      fetchModels: "Fetch models",
      chooseModel: "Choose a model",
      fetchingModels: "Fetching models...",
      modelsFetched: "Model list updated.",
      clearApiKey: "Clear saved key",
      regenerate: "Regenerate",
      saveArticleToCard: "Save to Card",
      articleCardDestination: "Article card deck: ",
      articleCardSkipped: "Article card not created",
      saveApiSettings: "Save API settings",
      keySaved: "Key saved",
      noKey: "No key",
      enterNewKey: "Leave blank to keep saved key",
      apiSettingsSaved: "API settings saved.",
      testApiSettings: "Test current configuration",
      testingApiSettings: "Testing current configuration...",
      apiSettingsTested: "Configuration works and the model responded.",
      articleCardSettingSaved: "Article card setting saved.",
      articleCardSaved: "Article card created in",
      articleCardFailed: "Article saved, but card creation failed: ",
      apiMissingBaseUrl: "Enter an API base URL.",
      apiMissingModel: "Enter a model name.",
      toggleTranslation: "Show/hide translation",
      translateButtonShort: "TR",
      historyTitle: "Article History",
      historyEmpty: "No saved articles.",
      historyCards: "cards",
     historyClose: "Close",
      historyDecksHeading: "Decks",
      historyHeatmapHeading: "Dates",
      historyArticlesHeading: "Articles",
      historyNoDeck: "Choose a deck.",
      historyNoDate: "Choose a date.",
      historyArticlesCount: "articles",
      historyRecentDate: "Recent",
      historyAllDecks: "All decks",
      deleteArticle: "Delete article",
      deleteSelectedDay: "Clear selected date",
      deleteDayPrefix: "Clear",
      confirmDelete: "Click again to confirm",
      desktopSettingsTitle: "Settings",
      momoApiKey: "MoMo API",
      clearMomoApiKey: "Clear saved MoMo API",
      momoDayStart: "Day start",
      momoDayEnd: "Day end",
      saveDesktopSettings: "Save settings",
      desktopSettingsSaved: "Settings saved.",
      momoKeySaved: "MoMo API saved",
      momoNoKey: "No MoMo API",
      enterNewMomoKey: "Leave blank to keep saved MoMo API",
     writingHorizontal: "横",
     writingVertical: "縦",
    },
    ja: {
      group_light: "🌞 ライト＆フレッシュ",
      group_retro: "☕ ウォーム＆レトロ",
      group_dark: "🌑 ダーク＆ミニマル",
      group_neon: "⚡ サイバー＆ネオン",

      theme_macchiato: "マキアート",
      theme_rosegold: "ローズゴールド",
      theme_forest: "深い森",
      theme_sunset: "砂丘の蜃気楼",
      theme_glacier: "氷河",
      theme_neontokyo: "ネオントーキョー",
      theme_lunarslate: "月の裏側",
      theme_midnightjazz: "ミッドナイトジャズ",
      theme_retromac: "レトロ Mac 1984",
      theme_abyss: "アビス",
      theme_cyberpunk: "サイバーパンク 2077",

      theme_light: "ライト",
      theme_dark: "ダーク",
      theme_oled: "OLED ヴォイド",
      theme_dracula: "ドラキュラ",
      theme_cyberviolet: "サイバーバイオレット",
      theme_lavender: "ラベンダーの黄昏",
      theme_gruvbox: "グルーヴボックス",
      theme_nord: "ノード",
      theme_matcha: "抹茶",
      theme_amethyst: "アメジスト",
      theme_eink: "E-ink ペーパー",
      theme_sepia: "セピア",
      theme_oceanic: "オーシャニック",
      theme_sakura: "桜",
      theme_glass: "グラスモーフィズム",
      theme_outrun: "アウトラン",

      eyebrow: "毎日の AI 読解",
      title: "読解で復習",
      sources: "学習元",
      decks: "今日のデッキ",
      fields: "AI フィールド",
      cards: "カード",
      article: "文章",
      settings: "API 設定",
      refresh: "更新",
      retry: "再試行",
      ankiConnectOffline: "AnkiConnect に接続できません。Anki を起動し、AnkiConnect がインストールされ有効になっていることを確認してください。",
      all: "全選択",
      invert: "反転",
      save: "保存",
      generate: "生成",
      new: "新規",
      delete: "削除",
      generating: "生成中...",
      returnToSelection: "選択に戻る",
      loadingDay: "Anki の日付を読み込み中...",
      selectDeck: "今日学習したデッキを選んでください。",
      noStudy: "この Anki 日には学習記録がありません。",
      noDecks: "この Anki 日に学習したデッキはありません。",
      loadingCards: "カードを読み込み中...",
      ready: "生成できます。",
      noCards: "このデッキには今日の候補カードがありません。",
      noFields: "利用できるフィールドがありません。",
      chooseField: "AI に渡すフィールドを 1 つ以上選んでください。",
      chooseCard: "カードを 1 枚以上選んでください。",
      fieldSaved: "フィールド設定を保存しました。",
      presetSaved: "プロンプトプリセットを保存しました。",
      presetUpdated: "プロンプトプリセットを更新しました。",
      savedArticle: "文章を保存しました：",
      markdownPath: "Markdown",
      htmlPath: "HTML",
      sourceDeck: "元デッキ",
      generatedAt: "生成日時",
      reviewNotes: "復習メモ",
      reviewNotesEmpty: "復習メモはまだありません。",
      readingTabArticle: "文章",
      readingTabNotes: "ノート",
      sourceTerms: "元の語句",
      fallbackTitle: "読解文章",
      selectDeckShort: "デッキを選択",
      candidateCards: "候補カード",
      selectedCards: "選択中",
      selectNewCards: "新規",
      selectFailedCards: "忘却",
      selectVagueCards: "曖昧",
      clearCardSelection: "クリア",
      cardsUnit: "カード",
      newCount: "新規",
      failedCount: "失敗",
      vagueCount: "曖昧",
      reviews: "回復習",
      childDecks: "子デッキ",
      expandCollapse: "展開または折りたたみ",
      presetName: "プリセット名",
      readerNativeLanguage: "読者の母語",
      articleLanguage: "生成記事の言語",
      difficulty: "難度",
      maxWords: "文字数範囲",
      instructions: "フォーマット要件",
      provider: "プロバイダー",
      baseUrl: "Base URL",
      model: "モデル",
      apiKey: "API key",
      temperature: "温度",
      maxTokens: "最大 tokens",
      fetchModels: "モデル取得",
      chooseModel: "モデルを選択",
      fetchingModels: "モデルを取得中...",
      modelsFetched: "モデル一覧を更新しました。",
      clearApiKey: "保存済み key を消去",
      regenerate: "再生成",
      saveArticleToCard: "カードに保存",
      articleCardDestination: "文章カードのデッキ：",
      articleCardSkipped: "文章カードは作成していません",
      saveApiSettings: "API 設定を保存",
      keySaved: "Key 保存済み",
      noKey: "Key なし",
      enterNewKey: "空欄なら保存済み key を保持",
      apiSettingsSaved: "API 設定を保存しました。",
      testApiSettings: "現在の設定をテスト",
      testingApiSettings: "現在の設定をテスト中...",
      apiSettingsTested: "設定は使用可能で、モデルへの接続に成功しました。",
      articleCardSettingSaved: "文章カード設定を保存しました。",
      articleCardSaved: "文章カードを作成しました：",
      articleCardFailed: "文章は保存しましたが、カード作成に失敗しました：",
      apiMissingBaseUrl: "API Base URL を入力してください。",
      apiMissingModel: "モデル名を入力してください。",
      toggleTranslation: "翻訳の表示/非表示",
      translateButtonShort: "訳",
      historyTitle: "過去の記事",
      historyEmpty: "保存された記事はありません。",
      historyCards: "カード",
     historyClose: "閉じる",
      historyDecksHeading: "デッキ",
      historyHeatmapHeading: "日付",
      historyArticlesHeading: "記事",
      historyNoDeck: "デッキを選んでください。",
      historyNoDate: "日付を選んでください。",
      historyArticlesCount: "件",
      historyRecentDate: "最近",
      historyAllDecks: "すべてのデッキ",
      deleteArticle: "記事を削除",
      deleteSelectedDay: "選択した日付を削除",
      deleteDayPrefix: "削除",
      confirmDelete: "もう一度クリックして確認",
      desktopSettingsTitle: "設定",
      momoApiKey: "MoMo API",
      clearMomoApiKey: "保存済み MoMo API を消去",
      momoDayStart: "1日の開始",
      momoDayEnd: "1日の終了",
      saveDesktopSettings: "設定を保存",
      desktopSettingsSaved: "設定を保存しました。",
      momoKeySaved: "MoMo API 保存済み",
      momoNoKey: "MoMo API なし",
      enterNewMomoKey: "空欄なら保存済み MoMo API を保持",
     writingHorizontal: "横",
     writingVertical: "縦",
    },
  };

  function tr(key) {
    const lang = I18N[state.uiLanguage];
    if (lang && Object.prototype.hasOwnProperty.call(lang, key)) return lang[key];
    if (Object.prototype.hasOwnProperty.call(I18N.en, key)) return I18N.en[key];
    return key;
  }

  function renderStatus() {
    let msg = tr(state.statusData.key);
    if (state.statusData.params.deckName) {
      msg = msg + state.statusData.params.deckName + ".";
    }
    if (state.statusData.params.message) {
      msg = state.statusData.params.message; // fallback for raw message errors
    }
    el.status.textContent = msg;
    el.status.classList.toggle("error", state.statusData.isError);
  }

  function applyI18n() {
    el.eyebrowText.textContent = tr("eyebrow");
    el.titleText.textContent = tr("title");
    if (el.sourcesHeading) el.sourcesHeading.textContent = tr("sources");
    el.decksHeading.textContent = tr("decks");
    el.fieldsHeading.textContent = tr("fields");
    el.cardsHeading.textContent = tr("cards");
    el.articleHeading.textContent = tr("article");
    el.settingsHeading.textContent = tr("settings");
    el.refreshButton.title = tr("refresh");
    el.selectAllFieldsButton.textContent = tr("all");
    el.invertFieldsButton.textContent = tr("invert");
    el.saveFieldsButton.textContent = tr("save");
    el.selectAllCardsButton.textContent = tr("all");
    el.selectNewCardsButton.textContent = tr("selectNewCards");
    el.selectFailedCardsButton.textContent = tr("selectFailedCards");
    el.selectVagueCardsButton.textContent = tr("selectVagueCards");
    el.clearCardSelectionButton.textContent = tr("clearCardSelection");
    el.generateButton.textContent = tr("generate");
    el.newPresetButton.textContent = tr("new");
    el.savePresetButton.textContent = tr("save");
    el.deletePresetButton.textContent = tr("delete");
    el.presetName.placeholder = tr("presetName");
    el.presetReaderNativeLanguage.placeholder = tr("readerNativeLanguage");
    el.presetArticleLanguage.placeholder = tr("articleLanguage");
    el.presetDifficulty.placeholder = tr("difficulty");
    el.presetMaxWords.placeholder = tr("maxWords");
    el.presetInstructions.placeholder = tr("instructions");
    el.providerLabel.textContent = tr("provider");
    el.baseUrlLabel.textContent = tr("baseUrl");
    el.modelLabel.textContent = tr("model");
    el.apiKeyLabel.textContent = tr("apiKey");
    el.temperatureLabel.textContent = tr("temperature");
    el.maxTokensLabel.textContent = tr("maxTokens");
    el.fetchModelsButton.textContent = tr("fetchModels");
    el.testApiSettingsButton.textContent = tr("testApiSettings");
    el.clearApiKeyLabel.textContent = tr("clearApiKey");
    if (el.regenerateButton) el.regenerateButton.textContent = tr("regenerate");
    if (el.saveArticleToCardButton) el.saveArticleToCardButton.textContent = tr("saveArticleToCard");
    renderArticleCardDestination();
    el.saveApiSettingsButton.textContent = tr("saveApiSettings");
    el.apiKeyInput.placeholder = state.apiSettings.hasApiKey ? tr("enterNewKey") : "";
    el.apiKeyStatus.textContent = state.apiSettings.hasApiKey ? tr("keySaved") : tr("noKey");
    el.uiLanguageSelect.value = state.uiLanguage;
    if (el.returnToSelectionButton) el.returnToSelectionButton.textContent = tr("returnToSelection");
    if (el.historyHeading) el.historyHeading.textContent = tr("historyTitle");
    if (el.historyButton) {
      el.historyButton.textContent = tr("historyTitle");
      el.historyButton.title = tr("historyTitle");
    }
    if (el.historyCloseButton) el.historyCloseButton.title = tr("historyClose");
    updateDeleteDayButton();
    if (el.deleteCurrentArticleButton) el.deleteCurrentArticleButton.textContent = tr("deleteArticle");
    if (el.desktopSettingsButton) {
      el.desktopSettingsButton.textContent = tr("desktopSettingsTitle");
      el.desktopSettingsButton.title = tr("desktopSettingsTitle");
    }
    if (el.desktopSettingsHeading) el.desktopSettingsHeading.textContent = tr("desktopSettingsTitle");
    if (el.desktopSettingsCloseButton) el.desktopSettingsCloseButton.title = tr("historyClose");
    if (el.momoApiKeyLabel) el.momoApiKeyLabel.textContent = tr("momoApiKey");
    if (el.clearMomoApiKeyLabel) el.clearMomoApiKeyLabel.textContent = tr("clearMomoApiKey");
    if (el.momoDayStartLabel) el.momoDayStartLabel.textContent = tr("momoDayStart");
    if (el.momoDayEndLabel) el.momoDayEndLabel.textContent = tr("momoDayEnd");
    if (el.saveDesktopSettingsButton) el.saveDesktopSettingsButton.textContent = tr("saveDesktopSettings");
    if (el.writingModeHorizontal) el.writingModeHorizontal.textContent = tr("writingHorizontal");
   if (el.writingModeVertical) el.writingModeVertical.textContent = tr("writingVertical");
    if (el.readingTabArticle) el.readingTabArticle.textContent = tr("readingTabArticle");
    if (el.readingTabNotes) el.readingTabNotes.textContent = tr("readingTabNotes");
    
    document.querySelectorAll('[data-i18n]').forEach(element => {
      const key = element.getAttribute('data-i18n');
      if (tr(key)) {
        if (element.tagName === 'OPTGROUP') {
          element.label = tr(key);
        } else {
          element.textContent = tr(key);
        }
      }
    });
   renderModelOptions();
    renderDesktopSettings();
    updateCardSelectionControls();
    
    if (state.dayStart && state.dayEnd) {
      el.dayWindow.textContent = `${formatTime(state.dayStart)} - ${formatTime(state.dayEnd)}`;
    }
    renderSources();
    if (state.decks.length) renderDecks();
    if (state.selectedDeckId) renderFields();
    if (state.selectedDeckId) renderCards(state.currentCards);
    renderStatus();
  }

  const bridgeQueue = [];
  let bridgeWaitStarted = false;

  function bridgeReady() {
    return typeof window.pycmd === "function";
  }

  function flushBridgeQueue() {
    if (!bridgeReady()) {
      return;
    }
    while (bridgeQueue.length) {
      window.pycmd(JSON.stringify(bridgeQueue.shift()));
    }
  }

  function waitForBridge() {
    if (bridgeWaitStarted) {
      return;
    }
    bridgeWaitStarted = true;
    var warned = false;
    const tick = () => {
      if (bridgeReady()) {
        flushBridgeQueue();
        return;
      }
      if (!warned) {
        console.warn(
          "DAIRR bridge is not available:",
          bridgeQueue.map(function (q) { return q.action; })
        );
        warned = true;
      }
      window.setTimeout(tick, 50);
    };
    tick();
  }

  function send(action, payload = {}) {
    if (
      window.__DAIRR_BRIDGE__ &&
      typeof window.__DAIRR_BRIDGE__.send === "function"
    ) {
      window.__DAIRR_BRIDGE__.send(action, payload);
      return;
    }

    bridgeQueue.push({ action: action, payload: payload });
    flushBridgeQueue();
    waitForBridge();
  }

  const destructiveTimers = new WeakMap();

  function resetDestructiveButton(button) {
    const timer = destructiveTimers.get(button);
    if (timer) window.clearTimeout(timer);
    destructiveTimers.delete(button);
    button.dataset.confirming = "false";
    if (button.dataset.originalText) button.textContent = button.dataset.originalText;
    button.classList.remove("confirming");
  }

  function confirmInPlace(button, action) {
    if (button.dataset.confirming === "true") {
      resetDestructiveButton(button);
      action();
      return;
    }
    button.dataset.originalText = button.textContent;
    button.dataset.confirming = "true";
    button.textContent = tr("confirmDelete");
    button.classList.add("confirming");
    destructiveTimers.set(button, window.setTimeout(() => resetDestructiveButton(button), 4000));
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatTime(seconds) {
    const date = new Date(seconds * 1000);
    return date.toLocaleString(state.uiLanguage || [], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function renderDecks() {
    if (!state.decks.length) {
      el.deckList.innerHTML = `<div class="empty">${tr("noDecks")}</div>`;
      return;
    }

    const rows = buildDeckRows();
    el.deckList.innerHTML = rows
      .map((row) => {
        const indent = `style="padding-left: ${12 + row.depth * 18}px"`;
        const selected = row.deck.id === state.selectedDeckId ? " selected" : "";
        const groupClass = row.deck.isGroup ? " aggregate" : "";
        const collapsed = state.collapsedDeckGroups.has(row.deck.name);
        const caret = row.hasChildren
          ? `<button class="deck-caret" data-collapse-path="${escapeHtml(row.deck.name)}" title="${tr("expandCollapse")}">${collapsed ? "▸" : "▾"}</button>`
          : '<span class="deck-caret-spacer"></span>';
        const childStats = row.hasChildren ? `<span>${row.childCount} ${tr("childDecks")}</span>` : "";
        return `
          <div class="deck-item${selected}${groupClass}" data-deck-id="${escapeHtml(row.deck.id)}" ${indent}>
            <div class="deck-name">${caret}<span>${escapeHtml(row.label)}</span></div>
            <div class="deck-stats">
              <span>${row.deck.totalCount} ${tr("cardsUnit")}</span>
              <span>${row.deck.newCount} ${tr("newCount")}</span>
              <span>${row.deck.failedCount} ${tr("failedCount")}</span>
              ${childStats}
            </div>
          </div>
        `;
      })
      .join("");

    document.querySelectorAll(".deck-caret").forEach((item) => {
      item.addEventListener("click", (event) => {
        event.stopPropagation();
        const path = item.dataset.collapsePath;
        if (state.collapsedDeckGroups.has(path)) {
          state.collapsedDeckGroups.delete(path);
        } else {
          state.collapsedDeckGroups.add(path);
        }
        send("saveCollapsedDeckGroups", {
          collapsedDeckGroups: Array.from(state.collapsedDeckGroups),
        });
        renderDecks();
      });
    });

    document.querySelectorAll(".deck-item[data-deck-id]").forEach((item) => {
      item.addEventListener("click", () => {
        selectDeck(item.dataset.deckId);
      });
    });
  }

  function renderSources() {
    if (!el.sourceList) return;
    if (!state.sources.length) {
      el.sourceList.innerHTML = "";
      return;
    }
    el.sourceList.innerHTML = state.sources
      .map((source) => {
        const selected = source.id === state.selectedSourceId ? " selected" : "";
        return `<button class="source-item${selected}" data-source-id="${escapeHtml(source.id)}">${escapeHtml(source.name)}</button>`;
      })
      .join("");
    el.sourceList.querySelectorAll("[data-source-id]").forEach((item) => {
      item.addEventListener("click", () => selectSource(item.dataset.sourceId));
    });
  }

  function resetDeckSelection() {
    state.selectedDeckId = null;
    state.autoSelectedDeck = false;
    state.decks = [];
    state.fields = [];
    state.selectedFields = [];
    state.currentCards = [];
    state.selectedCardIds = new Set();
    el.saveFieldsButton.disabled = true;
    setFieldButtons(false);
    el.cardList.innerHTML = "";
    renderFields();
    updateCardSelectionControls();
  }

  function selectSource(sourceId) {
    if (!sourceId) return;
    state.selectedSourceId = sourceId;
    resetDeckSelection();
    renderSources();
    renderDecks();
    setStatus("loadingDay");
    send("selectSource", { sourceId });
  }

  function selectDeck(deckId) {
    state.selectedDeckId = deckId;
    el.saveFieldsButton.disabled = true;
    state.fields = [];
    state.selectedFields = [];
    state.currentCards = [];
    state.selectedCardIds = new Set();
    updateGenerateButton();
    renderArticleCardDestination();
    renderFields();

    if (el.articleScroll) el.articleScroll.innerHTML = "";
    if (el.readingHeader) {
      el.readingHeader.innerHTML = "";
      el.readingHeader.hidden = true;
    }
    if (el.notesPanel) el.notesPanel.innerHTML = "";
    el.savedPaths.innerHTML = "";
    setReadingMode(false);
    setStatus("loadingCards");
    renderDecks();
    send("selectDeck", { deckId: state.selectedDeckId });
  }

  function buildDeckRows() {
    const rows = [];
    const groupCounts = new Map();
    const groupNames = new Set();
    const sortedDecks = [...state.decks].sort((a, b) => a.name.localeCompare(b.name));
    sortedDecks.forEach((deck) => {
      const parts = deck.name.split("::");
      for (let i = 1; i < parts.length; i += 1) {
        const path = parts.slice(0, i).join("::");
        groupNames.add(path);
        groupCounts.set(path, (groupCounts.get(path) || 0) + 1);
      }
    });

    sortedDecks.forEach((deck) => {
      const parts = deck.name.split("::");
      let hidden = false;
      for (let i = 1; i < parts.length; i += 1) {
        const path = parts.slice(0, i).join("::");
        if (state.collapsedDeckGroups.has(path)) {
          hidden = true;
        }
      }
      if (!hidden) {
        const hasChildren = groupNames.has(deck.name);
        rows.push({
          kind: "deck",
          deck,
          label: parts[parts.length - 1],
          depth: parts.length - 1,
          hasChildren,
          childCount: groupCounts.get(deck.name) || 0,
        });
      }
    });
    return rows;
  }

  function chooseInitialDeck(lastSelectedDeckId) {
    if (state.autoSelectedDeck || state.selectedDeckId || !state.decks.length) {
      return;
    }
    const validIds = new Set(state.decks.map((deck) => deck.id));
    let deck = null;
    if (lastSelectedDeckId && validIds.has(lastSelectedDeckId)) {
      deck = state.decks.find((item) => item.id === lastSelectedDeckId);
    }
    if (!deck) {
      deck = state.decks.find((item) => !item.isGroup) || state.decks[0];
    }
    if (!deck) {
      return;
    }
    state.autoSelectedDeck = true;
    selectDeck(deck.id);
  }

  function renderCards(cards) {
    state.currentCards = cards || [];
    updateCardSelectionControls();
    if (!state.currentCards.length) {
      el.cardList.innerHTML = `<div class="empty">${tr("noCards")}</div>`;
      return;
    }

    el.cardList.innerHTML = state.currentCards
      .map((card) => {
        const cardId = String(card.cid);
        const checked = state.selectedCardIds.has(cardId) ? " checked" : "";
        const selected = checked ? " selected" : "";
        const f = String(card.first_response || "").toUpperCase();
        const isVague = f === "VAGUE";

        const tags = [
          card.is_new ? `<span class="tag">${tr("newCount")}</span>` : "",
          card.is_failed ? `<span class="tag failed">${tr("failedCount")}</span>` : "",
          isVague ? `<span class="tag vague">${tr("vagueCount")}</span>` : "",
          `<span>${card.review_count} ${tr("reviews")}</span>`,
        ]
          .filter(Boolean)
          .join("");
        const fieldText = Object.entries(card.fields || {})
          .filter((entry) => entry[1] && entry[1] !== card.term)
          .slice(0, 2)
          .map((entry) => `${escapeHtml(entry[0])}: ${escapeHtml(entry[1])}`)
          .join("<br>");
        return `
          <label class="card-item${selected}">
            <input type="checkbox" value="${escapeHtml(cardId)}"${checked}>
            <span class="card-content">
              <span class="card-term">${escapeHtml(card.term)}</span>
              <span class="card-meta">${tags}</span>
              ${fieldText ? `<span class="card-meta card-fields">${fieldText}</span>` : ""}
            </span>
          </label>
        `;
      })
      .join("");
    el.cardList.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => {
        if (input.checked) {
          state.selectedCardIds.add(input.value);
        } else {
          state.selectedCardIds.delete(input.value);
        }
        input.closest(".card-item").classList.toggle("selected", input.checked);
        updateCardSelectionControls();
      });
    });
  }

  function renderFields() {
    if (!state.selectedDeckId) {
      el.fieldList.innerHTML = `<div class="empty" id="fieldEmptyText">${tr("selectDeckShort")}</div>`;
      setFieldButtons(false);
      return;
    }
    if (!state.fields.length) {
      el.fieldList.innerHTML = `<div class="empty" id="fieldEmptyText">${tr("noFields")}</div>`;
      setFieldButtons(false);
      return;
    }

    el.fieldList.innerHTML = state.fields
      .map((field) => {
        const checked = state.selectedFields.includes(field) ? " checked" : "";
        return `
          <label class="field-item">
            <input type="checkbox" value="${escapeHtml(field)}"${checked}>
            <span>${escapeHtml(field)}</span>
          </label>
        `;
      })
      .join("");

    el.fieldList.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => {
        state.selectedFields = Array.from(el.fieldList.querySelectorAll("input:checked"))
          .map((item) => item.value);
        el.saveFieldsButton.disabled = state.selectedFields.length === 0;
        updateGenerateButton();
      });
    });
    setFieldButtons(true);
    el.saveFieldsButton.disabled = state.selectedFields.length === 0;
    updateGenerateButton();
  }

  function setFieldButtons(enabled) {
    el.selectAllFieldsButton.disabled = !enabled;
    el.invertFieldsButton.disabled = !enabled;
    el.saveFieldsButton.disabled = !enabled;
  }

  function updateGenerateButton() {
    el.generateButton.disabled = !state.selectedDeckId
      || state.selectedFields.length === 0
      || state.selectedCardIds.size === 0;
  }

  function updateCardSelectionControls() {
    const total = state.currentCards.length;
    const selected = state.selectedCardIds.size;
    el.cardCount.textContent = state.selectedDeckId
      ? `${selected}/${total} ${tr("selectedCards")}`
      : tr("selectDeckShort");
    const hasCards = total > 0;
    el.selectAllCardsButton.disabled = !hasCards;
    el.selectNewCardsButton.disabled = !hasCards;
    el.selectFailedCardsButton.disabled = !hasCards;
    el.selectVagueCardsButton.disabled = !hasCards;
    el.clearCardSelectionButton.disabled = !hasCards || selected === 0;
    updateGenerateButton();
  }

  function selectCardsByPredicate(predicate) {
    state.currentCards
      .filter(predicate)
      .forEach((card) => state.selectedCardIds.add(String(card.cid)));
    renderCards(state.currentCards);
  }

  function renderPresets() {
    if (!state.promptPresets.length) {
      state.promptPresets = [{ id: "default", name: "Default", reader_native_language: "", article_language: "", difficulty: "", max_words: "", instructions: "" }];
    }
    el.presetSelect.innerHTML = state.promptPresets
      .map((preset) => {
        const selected = preset.id === state.selectedPromptPresetId ? " selected" : "";
        return `<option value="${escapeHtml(preset.id)}"${selected}>${escapeHtml(preset.name)}</option>`;
      })
      .join("");
    const preset = currentPreset();
    el.presetName.value = preset.name || "";
    if(el.presetReaderNativeLanguage) el.presetReaderNativeLanguage.value = preset.reader_native_language || "";
    if(el.presetArticleLanguage) el.presetArticleLanguage.value = preset.article_language || "";
    el.presetDifficulty.value = preset.difficulty || "";
    el.presetMaxWords.value = preset.max_words || "";
    el.presetInstructions.value = preset.instructions || "";
    el.deletePresetButton.disabled = preset.id === "default";
  }

  function renderApiSettings() {
    if (!state.providerProfiles.length) {
      state.providerProfiles = [{
        id: "custom",
        name: "Custom compatible API",
        base_url: "",
        model: "",
      }];
    }
    el.providerSelect.innerHTML = state.providerProfiles
      .map((profile) => {
        const selected = profile.id === state.apiSettings.providerId ? " selected" : "";
        return `<option value="${escapeHtml(profile.id)}"${selected}>${escapeHtml(profile.name)}</option>`;
      })
      .join("");
    const savedProfiles = state.apiSettings.profiles || [];
    el.apiProfileSelect.innerHTML = [`<option value="">${state.uiLanguage === "zh" ? "新建配置" : "New profile"}</option>`,
      ...savedProfiles.map((profile) => `<option value="${escapeHtml(profile.id)}"${profile.id === state.apiSettings.profileId ? " selected" : ""}>${escapeHtml(profile.name)}</option>`)
    ].join("");
    const activeProfile = savedProfiles.find((profile) => profile.id === state.apiSettings.profileId);
    el.apiProfileNameInput.value = activeProfile ? activeProfile.name : "";
    el.baseUrlInput.value = state.apiSettings.baseUrl || "";
    el.modelInput.value = state.apiSettings.model || "";
    el.temperatureInput.value = state.apiSettings.temperature;
    el.maxTokensInput.value = state.apiSettings.maxTokens;
    el.apiKeyInput.value = "";
    el.clearApiKeyInput.checked = false;
    el.clearApiKeyInput.disabled = !state.apiSettings.hasApiKey;
    el.apiKeyStatus.textContent = state.apiSettings.hasApiKey ? tr("keySaved") : tr("noKey");
    el.apiKeyInput.placeholder = state.apiSettings.hasApiKey ? tr("enterNewKey") : "";
    renderArticleCardDestination();
    renderModelOptions();
  }

  function renderDesktopSettings() {
    if (!el.momoApiKeyInput) return;
    const settings = state.desktopSettings || {};
    el.momoApiKeyInput.value = "";
    el.momoApiKeyInput.placeholder = settings.hasMomoApiKey ? tr("enterNewMomoKey") : "";
    el.clearMomoApiKeyInput.checked = false;
    el.clearMomoApiKeyInput.disabled = !settings.hasMomoApiKey;
    el.momoApiKeyStatus.textContent = settings.hasMomoApiKey ? tr("momoKeySaved") : tr("momoNoKey");
    el.momoDayStartInput.value = settings.momoDayStart || "04:00";
    el.momoDayEndInput.value = settings.momoDayEnd || "04:00";
  }

  function renderArticleCardDestination() {
    if (!el.articleCardDeckHint) return;
    const parentDeck = state.articleCardSettings.parentDeck || "Daily AI Reading Reinforcement";
    const deck = state.decks.find((item) => item.id === state.selectedDeckId);
    const targetDeck = deck ? `${parentDeck}::${deck.name}` : parentDeck;
    el.articleCardDeckHint.textContent = `${tr("articleCardDestination")}${targetDeck}`;
  }

  function currentProviderProfile() {
    return state.providerProfiles.find((profile) => profile.id === el.providerSelect.value);
  }

  function renderModelOptions() {
    if (!el.modelSelect) return;
    const options = state.modelOptions || [];
    el.modelSelect.disabled = options.length === 0;
    el.modelSelect.innerHTML = [
      `<option value="">${tr("chooseModel")}</option>`,
      ...options.map((model) => {
        const selected = model === el.modelInput.value ? " selected" : "";
        return `<option value="${escapeHtml(model)}"${selected}>${escapeHtml(model)}</option>`;
      }),
    ].join("");
  }

  function currentPreset() {
    return state.promptPresets.find((preset) => preset.id === state.selectedPromptPresetId)
      || state.promptPresets[0]
      || { id: "default", name: "Default", reader_native_language: "", article_language: "", difficulty: "", max_words: "", instructions: "" };
  }

  function currentPresetFormPayload() {
    return {
      id: state.selectedPromptPresetId,
      name: el.presetName.value,
      reader_native_language: el.presetReaderNativeLanguage ? el.presetReaderNativeLanguage.value : "",
      article_language: el.presetArticleLanguage ? el.presetArticleLanguage.value : "",
      difficulty: el.presetDifficulty.value,
      max_words: el.presetMaxWords.value,
      instructions: el.presetInstructions.value,
      prompt_template: "",
    };
  }

  function setStatus(key, isError = false, params = {}) {
    state.statusData = { key, isError, params };
    renderStatus();
  }

  function setProviderOffline(isOffline, message = "") {
    if (!el.providerOffline) return;
    el.providerOffline.hidden = !isOffline;
    if (isOffline && el.providerOfflineMessage) {
      el.providerOfflineMessage.textContent = message || tr("ankiConnectOffline");
    }
    if (el.providerRetryButton) el.providerRetryButton.textContent = tr("retry");
  }

  function extractBlock(raw, startMarker, endMarker) {
    const start = raw.indexOf(startMarker);
    if (start === -1) return "";
    const contentStart = start + startMarker.length;
    const end = endMarker ? raw.indexOf(endMarker, contentStart) : -1;
    return raw.slice(contentStart, end === -1 ? raw.length : end).trim();
  }

  function parseArticleResponse(rawArticle) {
    const raw = String(rawArticle || "").trim();
    const title = extractBlock(raw, "[ARTICLE_TITLE]", "[MAIN_ARTICLE]");
    const mainArticle = extractBlock(raw, "[MAIN_ARTICLE]", "[REVIEW_NOTES]");
    const reviewRaw = extractBlock(raw, "[REVIEW_NOTES]", "");
    if (!title && !mainArticle && !reviewRaw) {
      return {
        title: tr("fallbackTitle"),
        mainArticle: raw,
        reviewNotes: [],
        structured: false,
      };
    }
    return {
      title: title || tr("fallbackTitle"),
      mainArticle: mainArticle || raw,
      reviewNotes: parseReviewNotes(reviewRaw),
      structured: true,
    };
  }

  function parseReviewNotes(rawNotes) {
    return String(rawNotes || "")
      .split(/\n+/)
      .map((line) => line.trim().replace(/^[-*]\s*/, ""))
      .filter(Boolean)
      .map((line) => {
        const parts = line.split(/\s*::\s*/);
        if (parts.length >= 2) {
          return {
            term: parts.shift().trim(),
            note: parts.join(" :: ").trim(),
          };
        }
        const fallbackParts = line.split(/\s*[：:]\s*/);
        if (fallbackParts.length >= 2) {
          return {
            term: fallbackParts.shift().trim(),
            note: fallbackParts.join(": ").trim(),
          };
        }
        return { term: "", note: line };
      });
  }

  function renderParagraphs(text) {
    const raw = String(text || "");
    const lines = raw.split(/\n/);
    const segments = [];
    let currentParagraph = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();
      if (trimmed.match(/^\[T\]\s*/i)) {
        // This is a translation line
        const translation = trimmed.replace(/^\[T\]\s*/i, "").trim();
        if (currentParagraph.length > 0) {
          segments.push({
            paragraph: currentParagraph.join("\n").trim(),
            translation: translation,
          });
          currentParagraph = [];
        } else if (segments.length > 0) {
          // Attach to previous segment if no current paragraph
          segments[segments.length - 1].translation = translation;
        }
      } else if (trimmed === "") {
        // Empty line: flush current paragraph
        if (currentParagraph.length > 0) {
          segments.push({
            paragraph: currentParagraph.join("\n").trim(),
            translation: "",
          });
          currentParagraph = [];
        }
      } else {
        currentParagraph.push(line);
      }
    }
    // Flush remaining
    if (currentParagraph.length > 0) {
      segments.push({
        paragraph: currentParagraph.join("\n").trim(),
        translation: "",
      });
    }

    return segments
      .filter((seg) => seg.paragraph)
      .map((seg, idx) => {
        const bodyHtml = escapeHtml(seg.paragraph).replace(/\n/g, "<br>");
        if (!seg.translation) {
          return `<div class="reading-para-group"><p class="reading-para">${bodyHtml}</p></div>`;
        }
        const tId = `trans-${idx}`;
        const toggleHtml = `<button class="para-translate-toggle" type="button" ` +
          `onclick="(function(b){var el=document.getElementById('${tId}');var group=b.closest('.reading-para-group');var show=el.hidden;b.setAttribute('aria-expanded',show?'true':'false');el.hidden=!show;b.classList.toggle('open',show);if(group){group.classList.toggle('translation-open',show);}})(this)" ` +
          `title="${tr("toggleTranslation")}" aria-expanded="false">${escapeHtml(tr("translateButtonShort"))}</button>`;
        const translationHtml = `<div class="para-translation" id="${tId}" hidden>${escapeHtml(seg.translation)}</div>`;
        return `<div class="reading-para-group"><p class="reading-para">${bodyHtml} ${toggleHtml}</p>${translationHtml}</div>`;
      })
      .join("");
  }

  function renderReviewNotes(notes) {
    if (!notes.length) {
      return "";
    }
    return `
      <section class="review-notes">
        <h3>${tr("reviewNotes")}</h3>
        <dl>
          ${notes.map((item) => `
            ${item.term ? `<dt>${escapeHtml(item.term)}</dt>` : ""}
            <dd>${escapeHtml(item.note)}</dd>
          `).join("")}
        </dl>
      </section>
    `;
  }

  function renderArticle(payload) {
    const parsed = parseArticleResponse(payload.article);
    const generatedAt = payload.generatedAt || new Date().toLocaleString();
    state.readingHistoricalArticle = Boolean(payload.isHistorical);
    state.currentArticlePath = payload.markdownPath || "";
    state.currentArticleDay = payload.generatedDay || String(payload.generatedAt || "").slice(0, 10);
    document.body.classList.toggle("historical-reading", state.readingHistoricalArticle);
    const articleCardLine = payload.articleCard
      ? `<div>${tr("articleCardSaved")} ${escapeHtml(payload.articleCard.deckName)}</div>`
      : "";
    const articleCardSkippedLine = !payload.articleCard && !payload.articleCardError
      ? `<div>${tr("articleCardSkipped")}</div>`
      : "";
    const articleCardErrorLine = payload.articleCardError
      ? `<div class="save-warning">${tr("articleCardFailed")}${escapeHtml(payload.articleCardError)}</div>`
      : "";
    if (el.readingHeader) {
      el.readingHeader.innerHTML = `
        <div class="reading-kicker">${tr("sourceDeck")} · ${escapeHtml(payload.deckName || "")}</div>
        <h1>${escapeHtml(parsed.title)}</h1>
        <div class="reading-meta">${tr("generatedAt")} · ${escapeHtml(generatedAt)}</div>
      `;
      el.readingHeader.hidden = false;
    }
    el.articleScroll.innerHTML = `
      <div class="reading-document">
        <section class="reading-body">
          ${renderParagraphs(parsed.mainArticle)}
        </section>
      </div>
    `;
    const notesHtml = renderReviewNotes(parsed.reviewNotes);
    el.notesPanel.innerHTML = notesHtml
      ? notesHtml
      : `<div class="empty">${tr("reviewNotesEmpty")}</div>`;
    setReadingTab("article");
    el.savedPaths.innerHTML = `
      <details>
        <summary>${tr("savedArticle")}${escapeHtml(payload.deckName || "")}</summary>
        <div>${tr("markdownPath")}: ${escapeHtml(payload.markdownPath)}</div>
        <div>${tr("htmlPath")}: ${escapeHtml(payload.htmlPath)}</div>
        ${articleCardLine}
        ${articleCardSkippedLine}
        ${articleCardErrorLine}
      </details>
    `;
    setStatus("savedArticle", false, { deckName: payload.deckName });
    updateGenerateButton();
    setReadingMode(true);
    if (state.writingMode === "vertical") {
      alignVerticalArticleRight();
    }
  }

  function setReadingMode(active) {
    state.readingMode = active;
    document.body.classList.toggle("reading-mode", active);
    if (!active) {
      state.readingHistoricalArticle = false;
      state.currentArticlePath = "";
      state.currentArticleDay = "";
      document.body.classList.remove("historical-reading");
      state.writingMode = "horizontal";
      state.readingTab = "article";
      if (el.articleOutput) el.articleOutput.classList.remove("vertical-rl", "view-article", "view-notes");
    if (el.readingHeader) {
      el.readingHeader.innerHTML = "";
      el.readingHeader.hidden = true;
    }
      if (el.writingModeHorizontal) el.writingModeHorizontal.classList.add("active");
      if (el.writingModeVertical) el.writingModeVertical.classList.remove("active");
    }
  }

  function setReadingTab(tab) {
    state.readingTab = tab;
    if (el.articleOutput) {
      el.articleOutput.classList.remove("view-article", "view-notes");
      el.articleOutput.classList.add(tab === "notes" ? "view-notes" : "view-article");
    }
    if (el.readingTabArticle) el.readingTabArticle.classList.toggle("active", tab === "article");
    if (el.readingTabNotes) el.readingTabNotes.classList.toggle("active", tab === "notes");
  }

  if (el.readingTabArticle) {
    el.readingTabArticle.addEventListener("click", () => setReadingTab("article"));
  }
  if (el.readingTabNotes) {
    el.readingTabNotes.addEventListener("click", () => setReadingTab("notes"));
  }

  if (el.returnToSelectionButton) {
    el.returnToSelectionButton.addEventListener("click", () => {
      setReadingMode(false);
      updateGenerateButton();
    });
  }

  window.DAIRR = {
    receive(message) {
      const { event, payload } = message;
      if (event === "state") {
        setProviderOffline(false);
        state.decks = payload.decks || [];
        state.sources = payload.sources || [];
        state.selectedSourceId = payload.selectedSourceId || null;
        state.collapsedDeckGroups = new Set(payload.collapsedDeckGroups || []);
        state.promptPresets = payload.promptPresets || [];
        state.selectedPromptPresetId = payload.selectedPromptPresetId || "default";
        state.uiLanguage = payload.uiLanguage || state.uiLanguage;
        state.providerProfiles = payload.providerProfiles || [];
        state.apiSettings = payload.apiSettings || state.apiSettings;
        state.articleCardSettings = payload.articleCardSettings || state.articleCardSettings;
        state.desktopSettings = payload.desktopSettings || state.desktopSettings;
        state.dayStart = payload.dayStart;
        state.dayEnd = payload.dayEnd;
        el.dayWindow.textContent = `${formatTime(state.dayStart)} - ${formatTime(state.dayEnd)}`;
        updateGenerateButton();
        applyI18n();
        renderSources();
        renderDecks();
        renderPresets();
        renderApiSettings();
        renderDesktopSettings();
        setStatus(state.decks.length ? "selectDeck" : "noStudy");
        chooseInitialDeck(payload.lastSelectedDeckId || "");
      }
      if (event === "deckCards") {
        state.fields = payload.fields || [];
        state.selectedFields = payload.selectedFields || [];
        state.currentCards = payload.cards || [];
        state.selectedCardIds = new Set(state.currentCards.map((card) => String(card.cid)));
        renderFields();
        renderCards(state.currentCards);
        setStatus("ready");
      }
      if (event === "fieldConfigSaved") {
        state.selectedFields = payload.selectedFields || state.selectedFields;
        renderFields();
        setStatus("fieldSaved");
      }
      if (event === "generating") {
        el.generateButton.disabled = true;
        setStatus("generating", false, payload.message ? { message: payload.message } : {});
      }
      if (event === "promptPresets") {
        state.promptPresets = payload.promptPresets || [];
        state.selectedPromptPresetId = payload.selectedPromptPresetId || "default";
        renderPresets();
        setStatus("presetUpdated");
      }
      if (event === "apiSettingsSaved") {
        state.apiSettings = payload.apiSettings || state.apiSettings;
        renderApiSettings();
        applyI18n();
        setStatus("apiSettingsSaved");
      }
      if (event === "desktopSettingsSaved") {
        state.desktopSettings = payload.desktopSettings || state.desktopSettings;
        state.dayStart = payload.dayStart || state.dayStart;
        state.dayEnd = payload.dayEnd || state.dayEnd;
        if (state.dayStart && state.dayEnd) {
          el.dayWindow.textContent = `${formatTime(state.dayStart)} - ${formatTime(state.dayEnd)}`;
        }
        renderDesktopSettings();
        setStatus("desktopSettingsSaved");
        send("load");
      }
      if (event === "modelsFetched") {
        state.modelOptions = payload.models || [];
        renderModelOptions();
        el.fetchModelsButton.disabled = false;
        setStatus("modelsFetched");
      }
      if (event === "apiSettingsTested") {
        el.testApiSettingsButton.disabled = false;
        setStatus("apiSettingsTested");
      }
      if (event === "articleCardSettingsSaved") {
        state.articleCardSettings = payload.articleCardSettings || state.articleCardSettings;
        renderApiSettings();
        setStatus("articleCardSettingSaved");
      }
      if (event === "article") {
        state.lastGeneratedArticle = payload;
        if (el.saveArticleToCardButton) el.saveArticleToCardButton.disabled = false;
        renderArticle(payload);
      }
      if (event === "articleCardSaved") {
        if (el.saveArticleToCardButton) el.saveArticleToCardButton.disabled = false;
        if (payload.articleCardError) {
          setStatus("articleCardFailed", true, { message: payload.articleCardError });
        } else if (payload.articleCard) {
          setStatus("articleCardSaved", false, {
            deckName: payload.articleCard.deckName || payload.articleCard.deck || "",
          });
        } else {
          setStatus("articleCardSkipped", false);
        }
      }
      if (event === "providerOffline") {
        state.decks = [];
        state.selectedDeckId = null;
        state.fields = [];
        state.currentCards = [];
        state.selectedCardIds = new Set();
        renderDecks();
        renderFields();
        renderCards([]);
        updateGenerateButton();
        setProviderOffline(true, payload.message || tr("ankiConnectOffline"));
        setStatus("ankiConnectOffline", true);
      }
      if (event === "error") {
        updateGenerateButton();
        el.fetchModelsButton.disabled = false;
        el.testApiSettingsButton.disabled = false;
        setStatus("error", true, payload.message ? { message: payload.message } : {});
      }
      if (event === "articleList") {
        renderArticleHistory(payload.articles || []);
      }
      if (event === "articleLoaded") {
        closeHistoryPanel();
        const loadedPayload = {
          deckName: payload.deck || "",
          article: payload.article || "",
          markdownPath: payload.path || "",
          htmlPath: payload.htmlPath || "",
          generatedAt: payload.generated_at || "",
          generatedDay: payload.generated_day || "",
          isHistorical: true,
          articleCard: null,
        };
        // A historical document does not necessarily match the deck/cards
        // currently selected in the workspace, so it must never be saved as
        // a new card through that current selection.
        state.lastGeneratedArticle = null;
        if (el.saveArticleToCardButton) el.saveArticleToCardButton.disabled = true;
        renderArticle(loadedPayload);
      }
      if (event === "articleDeleted") {
        const deletedPath = payload.path || "";
        state.historyArticles = state.historyArticles.filter((item) => item.path !== deletedPath);
        if (state.currentArticlePath === deletedPath) setReadingMode(false);
        renderHistoryView();
      }
      if (event === "articlesDeleted") {
        state.historyArticles = [];
        if (state.currentArticlePath) setReadingMode(false);
        renderHistoryView();
      }
      if (event === "articlesDeletedByDay") {
        const deletedDay = payload.generatedDay || "";
        state.historyArticles = state.historyArticles.filter(
          (item) => dateKeyFromArticle(item) !== deletedDay
        );
        if (state.currentArticleDay === deletedDay) setReadingMode(false);
        state.historySelectedDate = null;
        renderHistoryView();
      }
    },
  };

  function openHistoryPanel() {
    if (el.historyPanel) {
      closeDesktopSettingsPanel();
      state.historySelectedDeck = HISTORY_ALL_DECKS;
      state.historySelectedDate = null;
      el.historyPanel.style.display = "";
      send("listArticles");
    }
  }

  function openDesktopSettingsPanel() {
    if (el.desktopSettingsPanel) {
      closeHistoryPanel();
      renderDesktopSettings();
      el.desktopSettingsPanel.style.display = "";
    }
  }

  function closeDesktopSettingsPanel() {
    if (el.desktopSettingsPanel) {
      el.desktopSettingsPanel.style.display = "none";
    }
  }

  function dateKeyFromArticle(article) {
    const explicitDay = String(article.generated_day || "").trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(explicitDay)) return explicitDay;

    // Historical Markdown stored a local datetime only. Its day is already
    // unambiguous, so extract it directly instead of relying on WebKit's
    // implementation-dependent parsing of "YYYY-MM-DD HH:MM:SS".
    const legacyDay = String(article.generated_at || "").trim().slice(0, 10);
    return /^\d{4}-\d{2}-\d{2}$/.test(legacyDay) ? legacyDay : "";
  }

  function makeHistoryGroup(deck, label, articles) {
    const group = { deck, label, articles, dateCount: new Map(), latest: "" };
    articles.forEach((item) => {
      const date = dateKeyFromArticle(item);
      if (!date) return;
      group.dateCount.set(date, (group.dateCount.get(date) || 0) + 1);
      if (!group.latest || date > group.latest) group.latest = date;
    });
    return group;
  }

  function groupHistoryByDeck(articles) {
    const map = new Map();
    articles.forEach((item) => {
      const deck = item.deck || item.filename || tr("fallbackTitle");
      if (!map.has(deck)) {
        map.set(deck, []);
      }
      map.get(deck).push(item);
    });
    const deckGroups = Array.from(map.entries())
      .map(([deck, deckArticles]) => makeHistoryGroup(deck, deck, deckArticles))
      .sort((a, b) => b.latest.localeCompare(a.latest));
    return [makeHistoryGroup(HISTORY_ALL_DECKS, tr("historyAllDecks"), articles), ...deckGroups];
  }

  function renderHistoryDecks(deckGroups) {
    if (!el.historyDecks) return;
    if (!deckGroups.length) {
      el.historyDecks.innerHTML = `<div class="empty">${tr("historyEmpty")}</div>`;
      return;
    }
    el.historyDecks.innerHTML = deckGroups
      .map((group) => {
        const selected = group.deck === state.historySelectedDeck ? " selected" : "";
        const count = group.articles.length;
        const latest = group.latest ? group.latest : "—";
        return `
          <div class="history-deck-item${selected}" data-deck="${escapeHtml(group.deck)}">
            <div class="history-deck-name">${escapeHtml(group.label)}</div>
            <div class="history-deck-meta">
              <span>${count} ${tr("historyArticlesCount")}</span>
              <span>${tr("historyRecentDate")} ${escapeHtml(latest)}</span>
            </div>
          </div>
        `;
      })
      .join("");
    el.historyDecks.querySelectorAll(".history-deck-item").forEach((item) => {
      item.addEventListener("click", () => {
        state.historySelectedDeck = item.dataset.deck;
        state.historySelectedDate = null;
        renderHistoryView();
      });
    });
  }

  function renderHistoryHeatmap(deckGroups) {
    if (!el.historyHeatmap) return;
    const group = deckGroups.find((g) => g.deck === state.historySelectedDeck);
    if (!group) {
      el.historyHeatmap.innerHTML = `<div class="empty">${tr("historyNoDeck")}</div>`;
      return;
    }
    // Always render the most recent 52 calendar weeks. The range is anchored
    // to the local current day, rather than the newest saved article, so a
    // quiet period does not make the heatmap jump around or disappear.
    const end = new Date();
    end.setHours(0, 0, 0, 0);
    const start = new Date(end);
    start.setDate(start.getDate() - (51 * 7 + end.getDay()));
    const maxCount = Math.max(...group.dateCount.values(), 1);
    const cells = [];
    const weekdayLabels = ["S", "M", "T", "W", "T", "F", "S"];
    const labelCol = weekdayLabels.map((d) => `<div class="heatmap-weekday">${d}</div>`).join("");
    let cursor = new Date(start);
    while (cursor <= end) {
      const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(cursor.getDate()).padStart(2, "0")}`;
      const count = group.dateCount.get(key) || 0;
      let level = 0;
      if (count > 0) {
        level = Math.ceil((count / maxCount) * 4);
      }
      const selected = key === state.historySelectedDate ? " selected" : "";
      const title = `${key} · ${count} ${tr("historyArticlesCount")}`;
      cells.push(`<div class="heatmap-cell level-${level}${selected}" data-date="${key}" title="${escapeHtml(title)}"></div>`);
      cursor.setDate(cursor.getDate() + 1);
    }
    // Pad trailing cells to complete the last week column.
    while (cells.length % 7 !== 0) {
      cells.push(`<div class="heatmap-cell filler"></div>`);
    }
    el.historyHeatmap.innerHTML =
      `<div class="history-section-label">${tr("historyHeatmapHeading")}</div>` +
      `<div class="heatmap-grid">` +
      `<div class="heatmap-weekdays">${labelCol}</div>` +
      `<div class="heatmap-cells">${cells.join("")}</div>` +
      `</div>`;
    el.historyHeatmap.querySelectorAll(".heatmap-cell[data-date]").forEach((cell) => {
      cell.addEventListener("click", () => {
        state.historySelectedDate = state.historySelectedDate === cell.dataset.date
          ? null
          : cell.dataset.date;
        renderHistoryView();
      });
    });
  }

  function renderHistoryArticles(deckGroups) {
    if (!el.historyArticles) return;
    const group = deckGroups.find((g) => g.deck === state.historySelectedDeck);
    if (!group) {
      el.historyArticles.innerHTML = `<div class="empty">${tr("historyNoDeck")}</div>`;
      return;
    }
    let items = group.articles;
    if (state.historySelectedDate) {
      items = items.filter((item) => dateKeyFromArticle(item) === state.historySelectedDate);
    }
    if (!items.length) {
      el.historyArticles.innerHTML = `<div class="empty">${tr("historyNoDate")}</div>`;
      return;
    }
    items.sort((a, b) => String(b.generated_at || "").localeCompare(String(a.generated_at || "")));
    el.historyArticles.innerHTML =
      `<div class="history-section-label">${tr("historyArticlesHeading")}</div>` +
      items
        .map((item) => {
          return `
            <div class="history-item history-item-row" data-path="${escapeHtml(item.path)}">
              <div class="history-item-content">
                <div class="history-item-title">${escapeHtml(item.title || item.filename || item.deck)}</div>
                <div class="history-item-meta">
                  ${escapeHtml(item.generated_at || "")}
                  ${item.card_count ? ` · ${escapeHtml(item.card_count)} ${tr("historyCards")}` : ""}
                </div>
              </div>
              <button class="history-delete-button" type="button" title="${tr("deleteArticle")}">${tr("delete")}</button>
            </div>
          `;
        })
        .join("");
    el.historyArticles.querySelectorAll(".history-item").forEach((item) => {
      item.addEventListener("click", () => {
        send("loadArticle", { path: item.dataset.path });
      });
      const deleteButton = item.querySelector(".history-delete-button");
      if (deleteButton) deleteButton.addEventListener("click", (event) => {
        event.stopPropagation();
        confirmInPlace(deleteButton, () => send("deleteArticle", { path: item.dataset.path }));
      });
    });
  }

  function renderHistoryView() {
    const deckGroups = groupHistoryByDeck(state.historyArticles);
    renderHistoryDecks(deckGroups);
    renderHistoryHeatmap(deckGroups);
    renderHistoryArticles(deckGroups);
    updateDeleteDayButton();
  }

  function updateDeleteDayButton() {
    if (!el.deleteDayArticlesButton) return;
    resetDestructiveButton(el.deleteDayArticlesButton);
    el.deleteDayArticlesButton.disabled = !state.historySelectedDate;
    el.deleteDayArticlesButton.textContent = state.historySelectedDate
      ? `${tr("deleteDayPrefix")} ${state.historySelectedDate}`
      : tr("deleteSelectedDay");
  }

  function closeHistoryPanel() {
    if (el.historyPanel) {
      el.historyPanel.style.display = "none";
    }
  }

  function renderArticleHistory(articles) {
    state.historyArticles = articles || [];
    if (!state.historySelectedDeck && state.historyArticles.length) {
      state.historySelectedDeck = HISTORY_ALL_DECKS;
    }
    renderHistoryView();
  }

  function alignVerticalArticleRight() {
    if (!el.articleScroll) return;
    window.requestAnimationFrame(() => {
      const readingBody = el.articleScroll.querySelector(".reading-body");
      if (readingBody) {
        const availableHeight = Math.max(160, el.articleScroll.clientHeight - 56);
        readingBody.style.setProperty("--vertical-flow-height", `${availableHeight}px`);
      }
      const maxScrollLeft = el.articleScroll.scrollWidth - el.articleScroll.clientWidth;
      if (maxScrollLeft <= 0) return;
      el.articleScroll.scrollLeft = maxScrollLeft;
      if (el.articleScroll.scrollLeft === 0) {
        el.articleScroll.scrollLeft = -maxScrollLeft;
      }
    });
  }

  if (el.historyButton) {
    el.historyButton.addEventListener("click", () => {
      openHistoryPanel();
    });
  }

  if (el.historyCloseButton) {
    el.historyCloseButton.addEventListener("click", () => {
      closeHistoryPanel();
    });
  }

  if (el.deleteDayArticlesButton) {
    el.deleteDayArticlesButton.addEventListener("click", () => {
      if (!state.historySelectedDate) return;
      const selectedDay = state.historySelectedDate;
      confirmInPlace(el.deleteDayArticlesButton, () => {
        send("deleteArticlesByDay", { generatedDay: selectedDay });
      });
    });
  }

  if (el.deleteCurrentArticleButton) {
    el.deleteCurrentArticleButton.addEventListener("click", () => {
      if (!state.currentArticlePath) return;
      confirmInPlace(el.deleteCurrentArticleButton, () => {
        send("deleteArticle", { path: state.currentArticlePath });
      });
    });
  }

  if (el.desktopSettingsButton) {
    el.desktopSettingsButton.addEventListener("click", () => {
      openDesktopSettingsPanel();
    });
  }

  if (el.desktopSettingsCloseButton) {
    el.desktopSettingsCloseButton.addEventListener("click", () => {
      closeDesktopSettingsPanel();
    });
  }

  function setWritingMode(mode) {
    state.writingMode = mode;
    if (el.articleOutput) {
      el.articleOutput.classList.toggle("vertical-rl", mode === "vertical");
    }
    if (mode === "vertical" && el.articleScroll) {
      alignVerticalArticleRight();
    }
    if (el.writingModeHorizontal) {
      el.writingModeHorizontal.classList.toggle("active", mode === "horizontal");
    }
    if (el.writingModeVertical) {
      el.writingModeVertical.classList.toggle("active", mode === "vertical");
    }
  }

  if (el.writingModeHorizontal) {
    el.writingModeHorizontal.addEventListener("click", () => {
      setWritingMode("horizontal");
    });
  }

  if (el.writingModeVertical) {
    el.writingModeVertical.addEventListener("click", () => {
      setWritingMode("vertical");
    });
  }

  window.addEventListener("resize", () => {
    if (state.writingMode === "vertical") alignVerticalArticleRight();
  });

  if (el.regenerateButton) {
    el.regenerateButton.addEventListener("click", () => {
      el.generateButton.click();
    });
  }

  if (el.saveArticleToCardButton) {
    el.saveArticleToCardButton.addEventListener("click", () => {
      if (el.saveArticleToCardButton.disabled) return;
      if (state.readingHistoricalArticle) return;
      if (!state.lastGeneratedArticle) return;
      
      const payload = state.lastGeneratedArticle;
      
      el.saveArticleToCardButton.disabled = true;
      setStatus("generating", false, { message: "Saving to card..." });
      
      send("saveArticleCard", {
        deckId: state.selectedDeckId,
        cardIds: Array.from(state.selectedCardIds),
        article: payload.article,
        markdownPath: payload.markdownPath,
        htmlPath: payload.htmlPath
      });
    });
  }

  el.generateButton.addEventListener("click", () => {
    if (el.generateButton.disabled) return;
    if (!state.selectedDeckId) return;
    if (!state.selectedFields.length) {
      setStatus("chooseField", true);
      return;
    }
    if (!state.selectedCardIds.size) {
      setStatus("chooseCard", true);
      return;
    }

    if (el.articleScroll) el.articleScroll.innerHTML = "";
    if (el.readingHeader) {
      el.readingHeader.innerHTML = "";
      el.readingHeader.hidden = true;
    }
    if (el.notesPanel) el.notesPanel.innerHTML = "";
    el.savedPaths.innerHTML = "";
    setReadingMode(false);
    
    setStatus("generating", false);
    el.generateButton.disabled = true;
    send("generate", {
      deckId: state.selectedDeckId,
      presetId: state.selectedPromptPresetId,
      preset: currentPresetFormPayload(),
      cardIds: Array.from(state.selectedCardIds),
    });
  });

  el.selectAllFieldsButton.addEventListener("click", () => {
    state.selectedFields = [...state.fields];
    renderFields();
  });

  el.invertFieldsButton.addEventListener("click", () => {
    state.selectedFields = state.fields.filter((field) => !state.selectedFields.includes(field));
    renderFields();
  });

  function isForgottenCard(card) {
    const f = String(card.first_response || "").toUpperCase();
    const grades = Array.isArray(card.response_grades) ? card.response_grades : [];
    return f === "FORGET" || grades.includes(1) || Boolean(card.is_failed);
  }

  function isVagueCard(card) {
    const f = String(card.first_response || "").toUpperCase();
    const grades = Array.isArray(card.response_grades) ? card.response_grades : [];
    return f === "VAGUE" || grades.includes(2);
  }

  function isNewCard(card) {
    return Boolean(card.is_new);
  }

  el.selectAllCardsButton.addEventListener("click", () => {
    selectCardsByPredicate(() => true);
  });

  el.selectNewCardsButton.addEventListener("click", () => {
    selectCardsByPredicate(isNewCard);
  });

  el.selectFailedCardsButton.addEventListener("click", () => {
    selectCardsByPredicate(isForgottenCard);
  });

  el.selectVagueCardsButton.addEventListener("click", () => {
    selectCardsByPredicate(isVagueCard);
  });

  el.clearCardSelectionButton.addEventListener("click", () => {
    state.selectedCardIds = new Set();
    renderCards(state.currentCards);
  });

  let isDraggingCard = false;
  let dragSelectCardValue = true;

  el.cardList.addEventListener("mousedown", (e) => {
    const item = e.target.closest(".card-item");
    if (!item) return;
    isDraggingCard = true;
    const input = item.querySelector("input");
    if (e.target.tagName !== "INPUT") {
      e.preventDefault();
      dragSelectCardValue = !input.checked;
      input.checked = dragSelectCardValue;
      if (dragSelectCardValue) {
        state.selectedCardIds.add(input.value);
      } else {
        state.selectedCardIds.delete(input.value);
      }
      item.classList.toggle("selected", dragSelectCardValue);
      updateCardSelectionControls();
    } else {
      dragSelectCardValue = !input.checked;
    }
  });

  el.cardList.addEventListener("mouseover", (e) => {
    if (!isDraggingCard) return;
    const item = e.target.closest(".card-item");
    if (!item) return;
    const input = item.querySelector("input");
    if (input.checked !== dragSelectCardValue) {
      input.checked = dragSelectCardValue;
      if (dragSelectCardValue) {
        state.selectedCardIds.add(input.value);
      } else {
        state.selectedCardIds.delete(input.value);
      }
      item.classList.toggle("selected", dragSelectCardValue);
      updateCardSelectionControls();
    }
  });

  document.addEventListener("mouseup", () => {
    isDraggingCard = false;
  });

  el.saveFieldsButton.addEventListener("click", () => {
    if (!state.selectedDeckId) return;
    send("saveFieldConfig", {
      deckId: state.selectedDeckId,
      fields: state.selectedFields,
    });
  });

  el.presetSelect.addEventListener("change", () => {
    state.selectedPromptPresetId = el.presetSelect.value;
    renderPresets();
    send("selectPromptPreset", { presetId: state.selectedPromptPresetId });
  });

  el.uiLanguageSelect.addEventListener("change", () => {
    state.uiLanguage = el.uiLanguageSelect.value;
    applyI18n();
    renderDecks();
    renderFields();
    send("saveUiLanguage", { uiLanguage: state.uiLanguage });
    setStatus("selectDeck");
  });

  el.newPresetButton.addEventListener("click", () => {
    state.selectedPromptPresetId = `preset-${Date.now()}`;
    state.promptPresets.push({
      id: state.selectedPromptPresetId,
      name: "New Preset",
      reader_native_language: "",
      article_language: "",
      difficulty: "",
      max_words: "",
      instructions: "",
    });
    renderPresets();
  });

  el.savePresetButton.addEventListener("click", () => {
    send("savePromptPreset", {
      preset: currentPresetFormPayload(),
    });
  });

  el.deletePresetButton.addEventListener("click", () => {
    send("deletePromptPreset", { presetId: state.selectedPromptPresetId });
  });

  el.providerSelect.addEventListener("change", () => {
    const profile = currentProviderProfile();
    state.apiSettings.providerId = el.providerSelect.value;
    if (profile && profile.id !== "custom") {
      state.apiSettings.baseUrl = profile.base_url || "";
      state.apiSettings.model = profile.model || "";
    }
    state.modelOptions = [];
    renderApiSettings();
  });

  el.saveApiSettingsButton.addEventListener("click", () => {
    const baseUrl = el.baseUrlInput.value.trim();
    const model = el.modelInput.value.trim();
    if (!baseUrl) {
      setStatus("apiMissingBaseUrl", true);
      return;
    }
    if (!model) {
      setStatus("apiMissingModel", true);
      return;
    }
    send("saveApiSettings", {
      settings: {
        profileId: el.apiProfileSelect.value,
        profileName: el.apiProfileNameInput.value,
        providerId: el.providerSelect.value,
        baseUrl,
        model,
        apiKey: el.apiKeyInput.value,
        clearApiKey: el.clearApiKeyInput.checked,
        temperature: el.temperatureInput.value,
        maxTokens: el.maxTokensInput.value,
      },
    });
  });

  el.apiProfileSelect.addEventListener("change", () => {
    const profile = (state.apiSettings.profiles || []).find((item) => item.id === el.apiProfileSelect.value);
    if (!profile) {
      state.apiSettings.profileId = "";
      el.apiProfileNameInput.value = "";
      return;
    }
    state.apiSettings = Object.assign({}, state.apiSettings, profile, { profileId: profile.id, profiles: state.apiSettings.profiles });
    renderApiSettings();
    send("selectApiProfile", { profileId: profile.id });
  });

  if (el.saveDesktopSettingsButton) {
    el.saveDesktopSettingsButton.addEventListener("click", () => {
      send("saveDesktopSettings", {
        settings: {
          momoApiKey: el.momoApiKeyInput.value,
          clearMomoApiKey: el.clearMomoApiKeyInput.checked,
          momoDayStart: el.momoDayStartInput.value,
          momoDayEnd: el.momoDayEndInput.value,
        },
      });
    });
  }


  el.fetchModelsButton.addEventListener("click", () => {
    const baseUrl = el.baseUrlInput.value.trim();
    if (!baseUrl) {
      setStatus("apiMissingBaseUrl", true);
      return;
    }
    setStatus("fetchingModels");
    el.fetchModelsButton.disabled = true;
    send("fetchModels", {
      settings: {
        baseUrl,
        apiKey: el.apiKeyInput.value,
      },
    });
  });

  el.testApiSettingsButton.addEventListener("click", () => {
    const baseUrl = el.baseUrlInput.value.trim();
    const model = el.modelInput.value.trim();
    if (!baseUrl || !model) {
      setStatus(!baseUrl ? "apiMissingBaseUrl" : "apiMissingModel", true);
      return;
    }
    el.testApiSettingsButton.disabled = true;
    setStatus("testingApiSettings");
    send("testApiSettings", { settings: { baseUrl, model, apiKey: el.apiKeyInput.value } });
  });

  el.modelSelect.addEventListener("change", () => {
    if (el.modelSelect.value) {
      el.modelInput.value = el.modelSelect.value;
    }
  });

  el.refreshButton.addEventListener("click", () => {
    const sourceId = state.selectedSourceId;
    resetDeckSelection();
    if (sourceId) {
      selectSource(sourceId);
    } else {
      send("load");
    }
  });

  if (el.providerRetryButton) {
    el.providerRetryButton.addEventListener("click", () => {
      setStatus("loadingDay");
      if (state.selectedSourceId) {
        send("selectSource", { sourceId: state.selectedSourceId });
      } else {
        send("load");
      }
    });
  }

  send("load");
})();


// --- Theme Switching Logic ---
function initTheme() {
  const themeSelect = document.getElementById('themeSelect');
  if (!themeSelect) return;
  
  // Load saved theme or fallback to light
  const savedTheme = localStorage.getItem('dairr_theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  themeSelect.value = savedTheme;
  
  themeSelect.addEventListener('change', (e) => {
    const newTheme = e.target.value;
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('dairr_theme', newTheme);
    
    // Update color-scheme so native OS elements (like dropdown scrollbars) match theme
    setTimeout(() => {
      const bg = getComputedStyle(document.body).backgroundColor;
      const rgb = bg.match(/\d+/g);
      if (rgb && rgb.length >= 3) {
        const luma = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
        document.documentElement.style.colorScheme = luma < 128 ? 'dark' : 'light';
      }
    }, 50);
  });
  
  // Also run on initial load
  setTimeout(() => {
    const bg = getComputedStyle(document.body).backgroundColor;
    const rgb = bg.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      const luma = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
      document.documentElement.style.colorScheme = luma < 128 ? 'dark' : 'light';
    }
  }, 50);
}

// Initialize theme as soon as DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  if (navigator.userAgent.includes('Mac OS X')) {
    document.documentElement.classList.add('os-mac');
  } else {
    document.documentElement.classList.add('os-windows');
  }
  initTheme();
});
