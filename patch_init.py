import re

with open("addon/daily_ai_reading_reinforcement/__init__.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. DEFAULT_CONFIG
content = re.sub(
    r"    \"create_article_cards\": False,\n",
    r"",
    content
)

# 2. _on_bridge_cmd
bridge_action = """            elif action == "saveArticleCard":
                self._save_article_card(
                    str(payload.get("deckId", "")),
                    payload.get("cardIds"),
                    str(payload.get("article", "")),
                    str(payload.get("markdownPath", "")),
                    str(payload.get("htmlPath", "")),
                )
            elif action == "generate":"""
content = content.replace("            elif action == \"generate\":", bridge_action)

# 3. _save_article_card_settings
content = re.sub(
    r"        config\[\"create_article_cards\"\] = bool\(settings\.get\(\"createArticleCards\"\)\)\n",
    r"",
    content
)

# 4. _generate_article remove create_article_cards
create_article_cards_block = """            if bool(config.get("create_article_cards")):
                try:
                    result["articleCard"] = create_article_card(
                        payload["name"],
                        cards,
                        result["article"],
                        Path(result["markdownPath"]),
                        Path(result["htmlPath"]),
                    )
                except Exception as exc:
                    result["articleCardError"] = str(exc)"""

content = content.replace(create_article_cards_block, "")

# 5. _save_article_card implementation
save_card_impl = """    def _save_article_card(
        self,
        deck_id: str,
        selected_card_ids: Any,
        article: str,
        markdown_path: str,
        html_path: str,
    ) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit("error", {"message": "Select a deck with study activity first."})
            return

        cards = payload["cards"]
        if selected_card_ids is not None:
            selected_ids = card_id_set(selected_card_ids)
            if selected_ids:
                cards = [card for card in cards if card.cid in selected_ids]

        def task() -> dict[str, Any]:
            return create_article_card(
                payload["name"],
                cards,
                article,
                Path(markdown_path),
                Path(html_path),
            )

        def on_done(future: Any) -> None:
            try:
                article_card = future.result()
                self._emit("articleCardSaved", {"articleCard": article_card})
            except Exception as exc:
                self._emit("articleCardSaved", {"articleCardError": str(exc)})

        mw.taskman.run_in_background(task, on_done)

    def _generate_article("""

content = content.replace("    def _generate_article(", save_card_impl)

# 6. article_card_settings_payload
content = re.sub(
    r"        \"createArticleCards\": bool\(config\.get\(\"create_article_cards\"\)\),\n",
    r"",
    content
)

with open("addon/daily_ai_reading_reinforcement/__init__.py", "w", encoding="utf-8") as f:
    f.write(content)
