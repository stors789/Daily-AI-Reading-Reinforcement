(function () {
  const state = {
    selectedDeckId: null,
    decks: [],
    collapsedDeckGroups: new Set(),
    fields: [],
    selectedFields: [],
    promptPresets: [],
    selectedPromptPresetId: "default",
    uiLanguage: "zh",
    providerProfiles: [],
    apiSettings: {
      providerId: "openai",
      baseUrl: "https://api.openai.com/v1",
      model: "gpt-4.1-mini",
      temperature: 0.7,
      maxTokens: 1400,
      hasApiKey: false,
    },
    articleCardSettings: {
      createArticleCards: false,
      parentDeck: "Daily AI Reading Reinforcement",
      noteType: "Daily AI Reading Reinforcement Article",
    },
  };

  const el = {
    eyebrowText: document.getElementById("eyebrowText"),
    titleText: document.getElementById("titleText"),
    uiLanguageSelect: document.getElementById("uiLanguageSelect"),
    deckList: document.getElementById("deckList"),
    cardList: document.getElementById("cardList"),
    cardCount: document.getElementById("cardCount"),
    dayWindow: document.getElementById("dayWindow"),
    decksHeading: document.getElementById("decksHeading"),
    fieldsHeading: document.getElementById("fieldsHeading"),
    cardsHeading: document.getElementById("cardsHeading"),
    articleHeading: document.getElementById("articleHeading"),
    settingsHeading: document.getElementById("settingsHeading"),
    generateButton: document.getElementById("generateButton"),
    selectAllFieldsButton: document.getElementById("selectAllFieldsButton"),
    invertFieldsButton: document.getElementById("invertFieldsButton"),
    saveFieldsButton: document.getElementById("saveFieldsButton"),
    refreshButton: document.getElementById("refreshButton"),
    fieldList: document.getElementById("fieldList"),
    presetSelect: document.getElementById("presetSelect"),
    presetName: document.getElementById("presetName"),
    presetLanguage: document.getElementById("presetLanguage"),
    presetDifficulty: document.getElementById("presetDifficulty"),
    presetMaxWords: document.getElementById("presetMaxWords"),
    presetInstructions: document.getElementById("presetInstructions"),
    newPresetButton: document.getElementById("newPresetButton"),
    savePresetButton: document.getElementById("savePresetButton"),
    deletePresetButton: document.getElementById("deletePresetButton"),
    providerSelect: document.getElementById("providerSelect"),
    providerLabel: document.getElementById("providerLabel"),
    baseUrlLabel: document.getElementById("baseUrlLabel"),
    modelLabel: document.getElementById("modelLabel"),
    apiKeyLabel: document.getElementById("apiKeyLabel"),
    temperatureLabel: document.getElementById("temperatureLabel"),
    maxTokensLabel: document.getElementById("maxTokensLabel"),
    clearApiKeyLabel: document.getElementById("clearApiKeyLabel"),
    createArticleCardsLabel: document.getElementById("createArticleCardsLabel"),
    baseUrlInput: document.getElementById("baseUrlInput"),
    modelInput: document.getElementById("modelInput"),
    apiKeyInput: document.getElementById("apiKeyInput"),
    temperatureInput: document.getElementById("temperatureInput"),
    maxTokensInput: document.getElementById("maxTokensInput"),
    clearApiKeyInput: document.getElementById("clearApiKeyInput"),
    createArticleCardsInput: document.getElementById("createArticleCardsInput"),
    apiKeyStatus: document.getElementById("apiKeyStatus"),
    saveApiSettingsButton: document.getElementById("saveApiSettingsButton"),
    status: document.getElementById("status"),
    articleOutput: document.getElementById("articleOutput"),
    savedPaths: document.getElementById("savedPaths"),
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
      loadingDay: "正在读取 Anki 日期...",
      selectDeck: "选择一个今天学过的卡组。",
      noStudy: "这个 Anki 日没有找到学习记录。",
      noDecks: "这个 Anki 日没有学习过的卡组。",
      loadingCards: "正在读取卡片...",
      ready: "可以生成了。",
      noCards: "这个卡组今天没有候选卡片。",
      chooseField: "请至少选择一个 AI 输入字段。",
      fieldSaved: "字段选择已保存。",
      presetSaved: "提示词预设已保存。",
      presetUpdated: "提示词预设已更新。",
      savedArticle: "文章已保存：",
      selectDeckShort: "选择卡组",
      candidateCards: "张候选卡",
      cardsUnit: "张卡",
      newCount: "新学",
      failedCount: "失败",
      reviews: "次复习",
      childDecks: "个子卡组",
      presetName: "预设名称",
      language: "写作语言",
      difficulty: "难度",
      maxWords: "最大字数",
      instructions: "额外提示词要求",
      provider: "服务商",
      baseUrl: "Base URL",
      model: "模型",
      apiKey: "API key",
      temperature: "温度",
      maxTokens: "最大 tokens",
      clearApiKey: "清除已保存 key",
      createArticleCards: "生成后创建文章卡片",
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
      loadingDay: "Loading Anki day...",
      selectDeck: "Choose a deck studied today.",
      noStudy: "No study activity found for this Anki day.",
      noDecks: "No decks studied in this Anki day.",
      loadingCards: "Loading cards...",
      ready: "Ready to generate.",
      noCards: "No candidate cards in this deck today.",
      chooseField: "Choose at least one field for AI input.",
      fieldSaved: "Field selection saved.",
      presetSaved: "Prompt preset saved.",
      presetUpdated: "Prompt presets updated.",
      savedArticle: "Saved article for ",
      selectDeckShort: "Select a deck",
      candidateCards: "candidate cards",
      cardsUnit: "cards",
      newCount: "new",
      failedCount: "failed",
      reviews: "reviews",
      childDecks: "child decks",
      presetName: "Preset name",
      language: "Language",
      difficulty: "Difficulty",
      maxWords: "Max words",
      instructions: "Extra prompt instructions",
      provider: "Provider",
      baseUrl: "Base URL",
      model: "Model",
      apiKey: "API key",
      temperature: "Temperature",
      maxTokens: "Max tokens",
      clearApiKey: "Clear saved key",
      createArticleCards: "Create article cards after generation",
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
      loadingDay: "Anki の日付を読み込み中...",
      selectDeck: "今日学習したデッキを選んでください。",
      noStudy: "この Anki 日には学習記録がありません。",
      noDecks: "この Anki 日に学習したデッキはありません。",
      loadingCards: "カードを読み込み中...",
      ready: "生成できます。",
      noCards: "このデッキには今日の候補カードがありません。",
      chooseField: "AI に渡すフィールドを 1 つ以上選んでください。",
      fieldSaved: "フィールド設定を保存しました。",
      presetSaved: "プロンプトプリセットを保存しました。",
      presetUpdated: "プロンプトプリセットを更新しました。",
      savedArticle: "文章を保存しました：",
      selectDeckShort: "デッキを選択",
      candidateCards: "候補カード",
      cardsUnit: "カード",
      newCount: "新規",
      failedCount: "失敗",
      reviews: "回復習",
      childDecks: "子デッキ",
      presetName: "プリセット名",
      language: "執筆言語",
      difficulty: "難度",
      maxWords: "最大文字数",
      instructions: "追加プロンプト指示",
      provider: "プロバイダー",
      baseUrl: "Base URL",
      model: "モデル",
      apiKey: "API key",
      temperature: "温度",
      maxTokens: "最大 tokens",
      clearApiKey: "保存済み key を消去",
      createArticleCards: "生成後に文章カードを作成",
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
    },
  };

  function tr(key) {
    return (I18N[state.uiLanguage] && I18N[state.uiLanguage][key])
      || I18N.en[key]
      || key;
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
    el.generateButton.textContent = tr("generate");
    el.newPresetButton.textContent = tr("new");
    el.savePresetButton.textContent = tr("save");
    el.deletePresetButton.textContent = tr("delete");
    el.presetName.placeholder = tr("presetName");
    el.presetLanguage.placeholder = tr("language");
    el.presetDifficulty.placeholder = tr("difficulty");
    el.presetMaxWords.placeholder = tr("maxWords");
    el.presetInstructions.placeholder = tr("instructions");
    el.providerLabel.textContent = tr("provider");
    el.baseUrlLabel.textContent = tr("baseUrl");
    el.modelLabel.textContent = tr("model");
    el.apiKeyLabel.textContent = tr("apiKey");
    el.temperatureLabel.textContent = tr("temperature");
    el.maxTokensLabel.textContent = tr("maxTokens");
    el.clearApiKeyLabel.textContent = tr("clearApiKey");
    el.createArticleCardsLabel.textContent = tr("createArticleCards");
    el.saveApiSettingsButton.textContent = tr("saveApiSettings");
    el.apiKeyInput.placeholder = state.apiSettings.hasApiKey ? tr("enterNewKey") : "";
    el.apiKeyStatus.textContent = state.apiSettings.hasApiKey ? tr("keySaved") : tr("noKey");
    el.uiLanguageSelect.value = state.uiLanguage;
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
    return date.toLocaleString([], {
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
          ? `<button class="deck-caret" data-collapse-path="${escapeHtml(row.deck.name)}" title="Expand or collapse">${collapsed ? "▸" : "▾"}</button>`
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
        state.selectedDeckId = item.dataset.deckId;
        el.generateButton.disabled = false;
        el.saveFieldsButton.disabled = true;
        state.fields = [];
        state.selectedFields = [];
        renderFields();
        el.articleOutput.innerHTML = "";
        el.savedPaths.innerHTML = "";
        setStatus("Loading cards...");
        renderDecks();
        send("selectDeck", { deckId: state.selectedDeckId });
      });
    });
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

  function renderCards(cards) {
    el.cardCount.textContent = `${cards.length} ${tr("candidateCards")}`;
    if (!cards.length) {
      el.cardList.innerHTML = `<div class="empty">${tr("noCards")}</div>`;
      return;
    }

    el.cardList.innerHTML = cards
      .map((card) => {
        const tags = [
          card.is_new ? '<span class="tag">new</span>' : "",
          card.is_failed ? '<span class="tag failed">failed</span>' : "",
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
          <div class="card-item">
            <div class="card-term">${escapeHtml(card.term)}</div>
            <div class="card-meta">${tags}</div>
            ${fieldText ? `<div class="card-meta">${fieldText}</div>` : ""}
          </div>
        `;
      })
      .join("");
    setStatus(tr("ready"));
  }

  function renderFields() {
    if (!state.selectedDeckId) {
      el.fieldList.innerHTML = `<div class="empty">${tr("selectDeckShort")}</div>`;
      setFieldButtons(false);
      return;
    }
    if (!state.fields.length) {
      el.fieldList.innerHTML = '<div class="empty">No fields found</div>';
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
        el.generateButton.disabled = state.selectedFields.length === 0;
      });
    });
    setFieldButtons(true);
    el.saveFieldsButton.disabled = state.selectedFields.length === 0;
    el.generateButton.disabled = state.selectedFields.length === 0;
  }

  function setFieldButtons(enabled) {
    el.selectAllFieldsButton.disabled = !enabled;
    el.invertFieldsButton.disabled = !enabled;
    el.saveFieldsButton.disabled = !enabled;
  }

  function renderPresets() {
    if (!state.promptPresets.length) {
      state.promptPresets = [{ id: "default", name: "Default", language: "", difficulty: "", max_words: "", instructions: "" }];
    }
    el.presetSelect.innerHTML = state.promptPresets
      .map((preset) => {
        const selected = preset.id === state.selectedPromptPresetId ? " selected" : "";
        return `<option value="${escapeHtml(preset.id)}"${selected}>${escapeHtml(preset.name)}</option>`;
      })
      .join("");
    const preset = currentPreset();
    el.presetName.value = preset.name || "";
    el.presetLanguage.value = preset.language || "";
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
    el.createArticleCardsInput.checked = Boolean(state.articleCardSettings.createArticleCards);
    el.apiKeyStatus.textContent = state.apiSettings.hasApiKey ? tr("keySaved") : tr("noKey");
    el.apiKeyInput.placeholder = state.apiSettings.hasApiKey ? tr("enterNewKey") : "";
  }

  function currentProviderProfile() {
    return state.providerProfiles.find((profile) => profile.id === el.providerSelect.value);
  }

  function currentPreset() {
    return state.promptPresets.find((preset) => preset.id === state.selectedPromptPresetId)
      || state.promptPresets[0]
      || { id: "default", name: "Default", language: "", difficulty: "", max_words: "", instructions: "" };
  }

  function setStatus(message, isError = false) {
    el.status.textContent = message;
    el.status.classList.toggle("error", isError);
  }

  function renderArticle(payload) {
    const blocks = String(payload.article || "")
      .split(/\n{2,}/)
      .filter((block) => block.trim())
      .map((block) => `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`)
      .join("");
    const articleCardLine = payload.articleCard
      ? `<div>${tr("articleCardSaved")} ${escapeHtml(payload.articleCard.deckName)}</div>`
      : "";
    const articleCardErrorLine = payload.articleCardError
      ? `<div class="save-warning">${tr("articleCardFailed")}${escapeHtml(payload.articleCardError)}</div>`
      : "";
    el.articleOutput.innerHTML = blocks;
    el.savedPaths.innerHTML = `
      <div>Markdown: ${escapeHtml(payload.markdownPath)}</div>
      <div>HTML: ${escapeHtml(payload.htmlPath)}</div>
      ${articleCardLine}
      ${articleCardErrorLine}
    `;
    setStatus(`${tr("savedArticle")}${payload.deckName}.`);
    el.generateButton.disabled = false;
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
        el.dayWindow.textContent = `${formatTime(payload.dayStart)} - ${formatTime(payload.dayEnd)}`;
        el.generateButton.disabled = !state.selectedDeckId;
        applyI18n();
        renderDecks();
        renderPresets();
        renderApiSettings();
        setStatus(state.decks.length ? tr("selectDeck") : tr("noStudy"));
      }
      if (event === "deckCards") {
        state.fields = payload.fields || [];
        state.selectedFields = payload.selectedFields || [];
        renderFields();
        renderCards(payload.cards || []);
      }
      if (event === "fieldConfigSaved") {
        state.selectedFields = payload.selectedFields || state.selectedFields;
        renderFields();
        setStatus(tr("fieldSaved"));
      }
      if (event === "generating") {
        el.generateButton.disabled = true;
        setStatus(payload.message || "Generating...");
      }
      if (event === "promptPresets") {
        state.promptPresets = payload.promptPresets || [];
        state.selectedPromptPresetId = payload.selectedPromptPresetId || "default";
        renderPresets();
        setStatus(tr("presetUpdated"));
      }
      if (event === "apiSettingsSaved") {
        state.apiSettings = payload.apiSettings || state.apiSettings;
        renderApiSettings();
        applyI18n();
        setStatus(tr("apiSettingsSaved"));
      }
      if (event === "articleCardSettingsSaved") {
        state.articleCardSettings = payload.articleCardSettings || state.articleCardSettings;
        renderApiSettings();
        setStatus(tr("articleCardSettingSaved"));
      }
      if (event === "article") {
        renderArticle(payload);
      }
      if (event === "error") {
        el.generateButton.disabled = !state.selectedDeckId;
        setStatus(payload.message || "Something went wrong.", true);
      }
    },
  };

  el.generateButton.addEventListener("click", () => {
    if (!state.selectedDeckId) return;
    if (!state.selectedFields.length) {
      setStatus(tr("chooseField"), true);
      return;
    }
    el.articleOutput.innerHTML = "";
    el.savedPaths.innerHTML = "";
    send("generate", { deckId: state.selectedDeckId, presetId: state.selectedPromptPresetId });
  });

  el.selectAllFieldsButton.addEventListener("click", () => {
    state.selectedFields = [...state.fields];
    renderFields();
  });

  el.invertFieldsButton.addEventListener("click", () => {
    state.selectedFields = state.fields.filter((field) => !state.selectedFields.includes(field));
    renderFields();
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
    setStatus(tr("selectDeck"));
  });

  el.newPresetButton.addEventListener("click", () => {
    state.selectedPromptPresetId = `preset-${Date.now()}`;
    state.promptPresets.push({
      id: state.selectedPromptPresetId,
      name: "New Preset",
      language: "",
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
        language: el.presetLanguage.value,
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
      el.baseUrlInput.value = profile.base_url || "";
      el.modelInput.value = profile.model || "";
    }
  });

  el.saveApiSettingsButton.addEventListener("click", () => {
    const baseUrl = el.baseUrlInput.value.trim();
    const model = el.modelInput.value.trim();
    if (!baseUrl) {
      setStatus(tr("apiMissingBaseUrl"), true);
      return;
    }
    if (!model) {
      setStatus(tr("apiMissingModel"), true);
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

  el.createArticleCardsInput.addEventListener("change", () => {
    state.articleCardSettings.createArticleCards = el.createArticleCardsInput.checked;
    send("saveArticleCardSettings", {
      settings: {
        createArticleCards: state.articleCardSettings.createArticleCards,
      },
    });
  });

  el.refreshButton.addEventListener("click", () => {
    state.selectedDeckId = null;
    state.fields = [];
    state.selectedFields = [];
    el.generateButton.disabled = true;
    el.saveFieldsButton.disabled = true;
    setFieldButtons(false);
    el.cardList.innerHTML = "";
    renderFields();
    el.cardCount.textContent = tr("selectDeckShort");
    send("load");
  });

  send("load");
})();
