(function () {
  const state = {
    selectedDeckId: null,
    decks: [],
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
    statusData: { key: "selectDeck", isError: false, params: {} },
    readingMode: false,
    writingMode: "horizontal",
    dayStart: 0,
    dayEnd: 0,
  };

  const el = {
    eyebrowText: document.getElementById("eyebrowText"),
    titleText: document.getElementById("titleText"),
    uiLanguageSelect: document.getElementById("uiLanguageSelect"),
    deckList: document.getElementById("deckList"),
    cardList: document.getElementById("cardList"),
    cardCount: document.getElementById("cardCount"),
    selectFailedCardsButton: document.getElementById("selectFailedCardsButton"),
    selectAllCardsButton: document.getElementById("selectAllCardsButton"),
    selectNewCardsButton: document.getElementById("selectNewCardsButton"),
    clearCardSelectionButton: document.getElementById("clearCardSelectionButton"),
    dayWindow: document.getElementById("dayWindow"),
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
    status: document.getElementById("status"),
    articleOutput: document.getElementById("articleOutput"),
    savedPaths: document.getElementById("savedPaths"),
    historyButton: document.getElementById("historyButton"),
    historyPanel: document.getElementById("historyPanel"),
    historyHeading: document.getElementById("historyHeading"),
    historyList: document.getElementById("historyList"),
    historyCloseButton: document.getElementById("historyCloseButton"),
    historyEmptyText: document.getElementById("historyEmptyText"),
    writingModeButtons: document.getElementById("writingModeButtons"),
    writingModeHorizontal: document.getElementById("writingModeHorizontal"),
    writingModeVertical: document.getElementById("writingModeVertical"),
  };

  const I18N = {
    zh: {
      eyebrow: "每日 AI 阅读",
      title: "阅读巩固",
      decks: "今日卡组",
      fields: "AI 字段",
      cards: "卡片",
      article: "文章",
      settings: "API 设置",
      refresh: "刷新",
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
      sourceTerms: "来源词条",
      fallbackTitle: "阅读文章",
      selectDeckShort: "请选择卡组",
      candidateCards: "张候选卡",
      selectedCards: "已选",
      selectFailedCards: "失败",
      selectNewCards: "新学",
      clearCardSelection: "清空",
      cardsUnit: "张卡",
      newCount: "新学",
      failedCount: "失败",
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
      articleCardSettingSaved: "文章卡片设置已保存。",
      articleCardSaved: "文章卡片已创建到",
      articleCardFailed: "文章已保存，但创建卡片失败：",
      apiMissingBaseUrl: "请输入 API Base URL。",
      apiMissingModel: "请输入模型名称。",
      toggleTranslation: "显示/隐藏翻译",
      historyTitle: "历史文章",
      historyEmpty: "没有已保存的文章。",
      historyCards: "张卡片",
      historyClose: "关闭",
      writingHorizontal: "横",
      writingVertical: "竖",
    },
    en: {
      eyebrow: "Daily AI Reading",
      title: "Reading Reinforcement",
      decks: "Studied Decks",
      fields: "AI Fields",
      cards: "Cards",
      article: "Article",
      settings: "API Settings",
      refresh: "Refresh",
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
      sourceTerms: "Source terms",
      fallbackTitle: "Reading Article",
      selectDeckShort: "Choose a deck",
      candidateCards: "candidate cards",
      selectedCards: "selected",
      selectFailedCards: "Failed",
      selectNewCards: "New",
      clearCardSelection: "Clear",
      cardsUnit: "cards",
      newCount: "new",
      failedCount: "failed",
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
      articleCardSettingSaved: "Article card setting saved.",
      articleCardSaved: "Article card created in",
      articleCardFailed: "Article saved, but card creation failed: ",
      apiMissingBaseUrl: "Enter an API base URL.",
      apiMissingModel: "Enter a model name.",
      toggleTranslation: "Show/hide translation",
      historyTitle: "Article History",
      historyEmpty: "No saved articles.",
      historyCards: "cards",
      historyClose: "Close",
      writingHorizontal: "横",
      writingVertical: "縦",
    },
    ja: {
      eyebrow: "毎日の AI 読解",
      title: "読解で復習",
      decks: "今日のデッキ",
      fields: "AI フィールド",
      cards: "カード",
      article: "文章",
      settings: "API 設定",
      refresh: "更新",
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
      sourceTerms: "元の語句",
      fallbackTitle: "読解文章",
      selectDeckShort: "デッキを選択",
      candidateCards: "候補カード",
      selectedCards: "選択中",
      selectFailedCards: "失敗",
      selectNewCards: "新規",
      clearCardSelection: "クリア",
      cardsUnit: "カード",
      newCount: "新規",
      failedCount: "失敗",
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
      articleCardSettingSaved: "文章カード設定を保存しました。",
      articleCardSaved: "文章カードを作成しました：",
      articleCardFailed: "文章は保存しましたが、カード作成に失敗しました：",
      apiMissingBaseUrl: "API Base URL を入力してください。",
      apiMissingModel: "モデル名を入力してください。",
      toggleTranslation: "翻訳の表示/非表示",
      historyTitle: "過去の記事",
      historyEmpty: "保存された記事はありません。",
      historyCards: "カード",
      historyClose: "閉じる",
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
    el.selectFailedCardsButton.textContent = tr("selectFailedCards");
    el.selectNewCardsButton.textContent = tr("selectNewCards");
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
    if (el.historyButton) el.historyButton.title = tr("historyTitle");
    if (el.historyCloseButton) el.historyCloseButton.title = tr("historyClose");
    if (el.writingModeHorizontal) el.writingModeHorizontal.textContent = tr("writingHorizontal");
    if (el.writingModeVertical) el.writingModeVertical.textContent = tr("writingVertical");
    renderModelOptions();
    updateCardSelectionControls();
    
    if (state.dayStart && state.dayEnd) {
      el.dayWindow.textContent = `${formatTime(state.dayStart)} - ${formatTime(state.dayEnd)}`;
    }
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
    const tick = () => {
      if (bridgeReady()) {
        flushBridgeQueue();
        return;
      }
      window.setTimeout(tick, 50);
    };
    tick();
  }

  function send(action, payload = {}) {
    bridgeQueue.push({ action, payload });
    flushBridgeQueue();
    waitForBridge();
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
    el.articleOutput.innerHTML = "";
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
        const tags = [
          card.is_new ? `<span class="tag">${tr("newCount")}</span>` : "",
          card.is_failed ? `<span class="tag failed">${tr("failedCount")}</span>` : "",
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
    el.selectFailedCardsButton.disabled = !hasCards;
    el.selectNewCardsButton.disabled = !hasCards;
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

  function setStatus(key, isError = false, params = {}) {
    state.statusData = { key, isError, params };
    renderStatus();
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
        const pHtml = `<p>${escapeHtml(seg.paragraph).replace(/\n/g, "<br>")}</p>`;
        if (!seg.translation) return pHtml;
        const tId = `trans-${idx}`;
        return `${pHtml}<div class="translation-row">` +
          `<button class="translation-toggle" onclick="(function(b){var el=document.getElementById('${tId}');var show=el.style.display==='none';el.style.display=show?'block':'none';b.classList.toggle('open',show);})(this)" title="${tr("toggleTranslation")}">🌐</button>` +
          `<div class="translation-block" id="${tId}" style="display:none;">${escapeHtml(seg.translation)}</div>` +
          `</div>`;
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
    const generatedAt = new Date().toLocaleString();
    const articleCardLine = payload.articleCard
      ? `<div>${tr("articleCardSaved")} ${escapeHtml(payload.articleCard.deckName)}</div>`
      : "";
    const articleCardSkippedLine = !payload.articleCard && !payload.articleCardError
      ? `<div>${tr("articleCardSkipped")}</div>`
      : "";
    const articleCardErrorLine = payload.articleCardError
      ? `<div class="save-warning">${tr("articleCardFailed")}${escapeHtml(payload.articleCardError)}</div>`
      : "";
    el.articleOutput.innerHTML = `
      <div class="reading-document">
        <header class="reading-header">
          <div class="reading-kicker">${tr("sourceDeck")} · ${escapeHtml(payload.deckName || "")}</div>
          <h1>${escapeHtml(parsed.title)}</h1>
          <div class="reading-meta">${tr("generatedAt")} · ${escapeHtml(generatedAt)}</div>
        </header>
        <section class="reading-body">
          ${renderParagraphs(parsed.mainArticle)}
        </section>
        ${renderReviewNotes(parsed.reviewNotes)}
      </div>
    `;
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
  }

  function setReadingMode(active) {
    state.readingMode = active;
    document.body.classList.toggle("reading-mode", active);
    if (!active) {
      state.writingMode = "horizontal";
      if (el.articleOutput) el.articleOutput.classList.remove("vertical-rl");
      if (el.writingModeHorizontal) el.writingModeHorizontal.classList.add("active");
      if (el.writingModeVertical) el.writingModeVertical.classList.remove("active");
    }
  }

  if (el.returnToSelectionButton) {
    el.returnToSelectionButton.addEventListener("click", () => {
      setReadingMode(false);
    });
  }

  window.DAIRR = {
    receive(message) {
      const { event, payload } = message;
      if (event === "state") {
        state.decks = payload.decks || [];
        state.collapsedDeckGroups = new Set(payload.collapsedDeckGroups || []);
        state.promptPresets = payload.promptPresets || [];
        state.selectedPromptPresetId = payload.selectedPromptPresetId || "default";
        state.uiLanguage = payload.uiLanguage || state.uiLanguage;
        state.providerProfiles = payload.providerProfiles || [];
        state.apiSettings = payload.apiSettings || state.apiSettings;
        state.articleCardSettings = payload.articleCardSettings || state.articleCardSettings;
        state.dayStart = payload.dayStart;
        state.dayEnd = payload.dayEnd;
        el.dayWindow.textContent = `${formatTime(state.dayStart)} - ${formatTime(state.dayEnd)}`;
        updateGenerateButton();
        applyI18n();
        renderDecks();
        renderPresets();
        renderApiSettings();
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
      if (event === "modelsFetched") {
        state.modelOptions = payload.models || [];
        renderModelOptions();
        el.fetchModelsButton.disabled = false;
        setStatus("modelsFetched");
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
          setStatus("articleCardSaved", false, { deckName: payload.articleCard.deck });
        } else {
          setStatus("articleCardSkipped", false);
        }
      }
      if (event === "error") {
        updateGenerateButton();
        el.fetchModelsButton.disabled = false;
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
          articleCard: null,
        };
        state.lastGeneratedArticle = loadedPayload;
        if (el.saveArticleToCardButton) el.saveArticleToCardButton.disabled = false;
        renderArticle(loadedPayload);
      }
    },
  };

  function openHistoryPanel() {
    if (el.historyPanel) {
      el.historyPanel.style.display = "";
      send("listArticles");
    }
  }

  function closeHistoryPanel() {
    if (el.historyPanel) {
      el.historyPanel.style.display = "none";
    }
  }

  function renderArticleHistory(articles) {
    if (!el.historyList) return;
    if (!articles.length) {
      el.historyList.innerHTML = `<div class="empty">${tr("historyEmpty")}</div>`;
      return;
    }
    el.historyList.innerHTML = articles
      .map((item) => {
        return `
          <div class="history-item" data-path="${escapeHtml(item.path)}">
            <div class="history-item-title">${escapeHtml(item.deck || item.filename)}</div>
            <div class="history-item-meta">
              ${escapeHtml(item.generated_at || "")}
              ${item.card_count ? ` · ${escapeHtml(item.card_count)} ${tr("historyCards")}` : ""}
            </div>
          </div>
        `;
      })
      .join("");
    el.historyList.querySelectorAll(".history-item").forEach((item) => {
      item.addEventListener("click", () => {
        send("loadArticle", { path: item.dataset.path });
      });
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

  function setWritingMode(mode) {
    state.writingMode = mode;
    if (el.articleOutput) {
      el.articleOutput.classList.toggle("vertical-rl", mode === "vertical");
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

  if (el.regenerateButton) {
    el.regenerateButton.addEventListener("click", () => {
      el.generateButton.click();
    });
  }

  if (el.saveArticleToCardButton) {
    el.saveArticleToCardButton.addEventListener("click", () => {
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
    if (!state.selectedDeckId) return;
    if (!state.selectedFields.length) {
      setStatus("chooseField", true);
      return;
    }
    if (!state.selectedCardIds.size) {
      setStatus("chooseCard", true);
      return;
    }
    el.articleOutput.innerHTML = "";
    el.savedPaths.innerHTML = "";
    setReadingMode(false);
    send("generate", {
      deckId: state.selectedDeckId,
      presetId: state.selectedPromptPresetId,
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

  el.selectAllCardsButton.addEventListener("click", () => {
    selectCardsByPredicate(() => true);
  });

  el.selectFailedCardsButton.addEventListener("click", () => {
    selectCardsByPredicate((card) => Boolean(card.is_failed));
  });

  el.selectNewCardsButton.addEventListener("click", () => {
    selectCardsByPredicate((card) => Boolean(card.is_new));
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
      preset: {
        id: state.selectedPromptPresetId,
        name: el.presetName.value,
        reader_native_language: el.presetReaderNativeLanguage ? el.presetReaderNativeLanguage.value : "",
        article_language: el.presetArticleLanguage ? el.presetArticleLanguage.value : "",
        difficulty: el.presetDifficulty.value,
        max_words: el.presetMaxWords.value,
        instructions: el.presetInstructions.value,
        prompt_template: "",
      },
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

  el.modelSelect.addEventListener("change", () => {
    if (el.modelSelect.value) {
      el.modelInput.value = el.modelSelect.value;
    }
  });

  el.refreshButton.addEventListener("click", () => {
    state.selectedDeckId = null;
    state.autoSelectedDeck = false;
    state.fields = [];
    state.selectedFields = [];
    state.currentCards = [];
    state.selectedCardIds = new Set();
    el.saveFieldsButton.disabled = true;
    setFieldButtons(false);
    el.cardList.innerHTML = "";
    renderFields();
    updateCardSelectionControls();
    send("load");
  });

  send("load");
})();
