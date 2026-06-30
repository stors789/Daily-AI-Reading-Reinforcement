(function () {
  const state = {
    selectedDeckId: null,
    decks: [],
    fields: [],
    selectedFields: [],
  };

  const el = {
    deckList: document.getElementById("deckList"),
    cardList: document.getElementById("cardList"),
    cardCount: document.getElementById("cardCount"),
    dayWindow: document.getElementById("dayWindow"),
    generateButton: document.getElementById("generateButton"),
    saveFieldsButton: document.getElementById("saveFieldsButton"),
    refreshButton: document.getElementById("refreshButton"),
    fieldList: document.getElementById("fieldList"),
    status: document.getElementById("status"),
    articleOutput: document.getElementById("articleOutput"),
    savedPaths: document.getElementById("savedPaths"),
  };

  function send(action, payload = {}) {
    pycmd(JSON.stringify({ action, payload }));
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

    el.deckList.innerHTML = state.decks
      .map((deck) => {
        const selected = deck.id === state.selectedDeckId ? " selected" : "";
        return `
          <div class="deck-item${selected}" data-deck-id="${escapeHtml(deck.id)}">
            <div class="deck-name">${escapeHtml(deck.name)}</div>
            <div class="deck-stats">
              <span>${deck.totalCount} cards</span>
              <span>${deck.newCount} new</span>
              <span>${deck.failedCount} failed</span>
            </div>
          </div>
        `;
      })
      .join("");

    document.querySelectorAll(".deck-item").forEach((item) => {
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
      return;
    }
    if (!state.fields.length) {
      el.fieldList.innerHTML = '<div class="empty">No fields found</div>';
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
    el.saveFieldsButton.disabled = state.selectedFields.length === 0;
    el.generateButton.disabled = state.selectedFields.length === 0;
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
        el.dayWindow.textContent = `${formatTime(payload.dayStart)} - ${formatTime(payload.dayEnd)}`;
        el.generateButton.disabled = !state.selectedDeckId;
        renderDecks();
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
    send("generate", { deckId: state.selectedDeckId });
  });

  el.saveFieldsButton.addEventListener("click", () => {
    if (!state.selectedDeckId) return;
    send("saveFieldConfig", {
      deckId: state.selectedDeckId,
      fields: state.selectedFields,
    });
  });

  el.refreshButton.addEventListener("click", () => {
    state.selectedDeckId = null;
    state.fields = [];
    state.selectedFields = [];
    el.generateButton.disabled = true;
    el.saveFieldsButton.disabled = true;
    el.cardList.innerHTML = "";
    renderFields();
    el.cardCount.textContent = "Select a deck";
    send("load");
  });

  send("load");
})();
