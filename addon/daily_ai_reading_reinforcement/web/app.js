(function () {
  const state = {
    selectedDeckId: null,
    decks: [],
    collapsedDeckGroups: new Set(),
    fields: [],
    selectedFields: [],
    promptPresets: [],
    selectedPromptPresetId: "default",
  };

  const el = {
    deckList: document.getElementById("deckList"),
    cardList: document.getElementById("cardList"),
    cardCount: document.getElementById("cardCount"),
    dayWindow: document.getElementById("dayWindow"),
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
    presetInstructions: document.getElementById("presetInstructions"),
    newPresetButton: document.getElementById("newPresetButton"),
    savePresetButton: document.getElementById("savePresetButton"),
    deletePresetButton: document.getElementById("deletePresetButton"),
    status: document.getElementById("status"),
    articleOutput: document.getElementById("articleOutput"),
    savedPaths: document.getElementById("savedPaths"),
  };

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
      el.deckList.innerHTML = '<div class="empty">No decks studied in this Anki day.</div>';
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
        const childStats = row.hasChildren ? `<span>${row.childCount} child decks</span>` : "";
        return `
          <div class="deck-item${selected}${groupClass}" data-deck-id="${escapeHtml(row.deck.id)}" ${indent}>
            <div class="deck-name">${caret}<span>${escapeHtml(row.label)}</span></div>
            <div class="deck-stats">
              <span>${row.deck.totalCount} cards</span>
              <span>${row.deck.newCount} new</span>
              <span>${row.deck.failedCount} failed</span>
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
    el.cardCount.textContent = `${cards.length} candidate cards`;
    if (!cards.length) {
      el.cardList.innerHTML = '<div class="empty">No candidate cards in this deck today.</div>';
      return;
    }

    el.cardList.innerHTML = cards
      .map((card) => {
        const tags = [
          card.is_new ? '<span class="tag">new</span>' : "",
          card.is_failed ? '<span class="tag failed">failed</span>' : "",
          `<span>${card.review_count} reviews</span>`,
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
    setStatus("Ready to generate.");
  }

  function renderFields() {
    if (!state.selectedDeckId) {
      el.fieldList.innerHTML = '<div class="empty">Select a deck</div>';
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
      state.promptPresets = [{ id: "default", name: "Default", language: "", difficulty: "", instructions: "" }];
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
    el.presetInstructions.value = preset.instructions || "";
    el.deletePresetButton.disabled = preset.id === "default";
  }

  function currentPreset() {
    return state.promptPresets.find((preset) => preset.id === state.selectedPromptPresetId)
      || state.promptPresets[0]
      || { id: "default", name: "Default", language: "", difficulty: "", instructions: "" };
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
    el.articleOutput.innerHTML = blocks;
    el.savedPaths.innerHTML = `
      <div>Markdown: ${escapeHtml(payload.markdownPath)}</div>
      <div>HTML: ${escapeHtml(payload.htmlPath)}</div>
    `;
    setStatus(`Saved article for ${payload.deckName}.`);
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
        el.dayWindow.textContent = `${formatTime(payload.dayStart)} - ${formatTime(payload.dayEnd)}`;
        el.generateButton.disabled = !state.selectedDeckId;
        renderDecks();
        renderPresets();
        setStatus(state.decks.length ? "Choose a deck studied today." : "No study activity found for this Anki day.");
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
        setStatus("Field selection saved.");
      }
      if (event === "generating") {
        el.generateButton.disabled = true;
        setStatus(payload.message || "Generating...");
      }
      if (event === "promptPresets") {
        state.promptPresets = payload.promptPresets || [];
        state.selectedPromptPresetId = payload.selectedPromptPresetId || "default";
        renderPresets();
        setStatus(payload.message || "Prompt presets updated.");
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
      setStatus("Choose at least one field for AI input.", true);
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

  el.newPresetButton.addEventListener("click", () => {
    state.selectedPromptPresetId = `preset-${Date.now()}`;
    state.promptPresets.push({
      id: state.selectedPromptPresetId,
      name: "New Preset",
      language: "",
      difficulty: "",
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
        instructions: el.presetInstructions.value,
        prompt_template: "",
      },
    });
  });

  el.deletePresetButton.addEventListener("click", () => {
    send("deletePromptPreset", { presetId: state.selectedPromptPresetId });
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
    el.cardCount.textContent = "Select a deck";
    send("load");
  });

  send("load");
})();
