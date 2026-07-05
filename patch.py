import re

with open("addon/daily_ai_reading_reinforcement/web/app.js", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update elements
content = re.sub(
    r"generateButton: document\.getElementById\(\"generateButton\"\),",
    r"""generateButton: document.getElementById("generateButton"),
    regenerateButton: document.getElementById("regenerateButton"),
    saveArticleToCardButton: document.getElementById("saveArticleToCardButton"),""",
    content
)

content = re.sub(
    r"    createArticleCardsLabel: document\.getElementById\(\"createArticleCardsLabel\"\),\n",
    "",
    content
)

content = re.sub(
    r"    createArticleCardsInput: document\.getElementById\(\"createArticleCardsInput\"\),\n",
    "",
    content
)

# 2. Translations
content = re.sub(
    r"      createArticleCards: \"生成后保存为 Anki 文章卡片\",",
    r"""      regenerate: "重生成",
      saveArticleToCard: "保存到卡片",""",
    content
)

content = re.sub(
    r"      createArticleCards: \"Save as Anki article card after generation\",",
    r"""      regenerate: "Regenerate",
      saveArticleToCard: "Save to Card",""",
    content
)

content = re.sub(
    r"      createArticleCards: \"生成後に Anki 文章カードとして保存\",",
    r"""      regenerate: "再生成",
      saveArticleToCard: "カードに保存",""",
    content
)

# 3. applyI18n
content = re.sub(
    r"    el\.createArticleCardsLabel\.textContent = tr\(\"createArticleCards\"\);\n",
    r"""    if (el.regenerateButton) el.regenerateButton.textContent = tr("regenerate");
    if (el.saveArticleToCardButton) el.saveArticleToCardButton.textContent = tr("saveArticleToCard");
""",
    content
)

# 4. state.articleCardSettings.createArticleCards -> default false but remove checkbox code
content = re.sub(
    r"    el\.createArticleCardsInput\.checked = Boolean\(state\.articleCardSettings\.createArticleCards\);\n",
    "",
    content
)

content = re.sub(
    r"""  el\.createArticleCardsInput\.addEventListener\("change", \(\) => \{\n    state\.articleCardSettings\.createArticleCards = el\.createArticleCardsInput\.checked;\n    send\("saveArticleCardSettings", \{\n      settings: \{\n        createArticleCards: state\.articleCardSettings\.createArticleCards,\n      \},\n    \}\);\n  \}\);\n""",
    "",
    content
)

# 5. Handlers
handlers = """

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
"""

content = content.replace("el.generateButton.addEventListener(\"click\", () => {", handlers + "\n  el.generateButton.addEventListener(\"click\", () => {")

# 6. Save lastGeneratedArticle
content = content.replace(
    """      if (event === "article") {\n        renderArticle(payload);\n      }""",
    """      if (event === "article") {
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
      }"""
)

# 7. update createArticleCards state
content = re.sub(
    r"      createArticleCards: false,\n",
    r"",
    content
)

with open("addon/daily_ai_reading_reinforcement/web/app.js", "w", encoding="utf-8") as f:
    f.write(content)
