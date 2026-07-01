# Daily AI Reading Reinforcement Config

`api_key`
: Your OpenAI-compatible API key.

`base_url`
: API base URL. For OpenAI, use `https://api.openai.com/v1`.

`model`
: Chat completions model name.

`selected_provider_profile`
: Last selected API provider profile. The add-on UI uses this to prefill common OpenAI-compatible providers.

`temperature`
: Sampling temperature for the generated article.

`max_tokens`
: Maximum tokens for the AI response. Defaults to `30000`.

`prompt_template`
: Optional custom prompt. You can use `{reader_native_language}`, `{article_language}`, `{difficulty}`, `{length_instruction}`, `{instructions}`, `{deck_name}`, and `{cards}` placeholders.

`deck_field_config`
: Saved field selections for each deck. This is managed by the add-on UI.

`create_article_cards`
: When true, each generated article is also saved as an Anki note under `Daily AI Reading Reinforcement::<source deck>`.

`last_selected_deck_id`
: Last selected studied deck. This is managed by the add-on UI and used to auto-select a deck on open.

`collapsed_deck_groups`
: Saved collapsed parent deck paths. This is managed by the add-on UI.

`ui_language`
: UI language. Supported values are `zh`, `en`, and `ja`.

`prompt_presets`
: Saved prompt presets. Each preset can define reader native language, article language, difficulty, word range such as `300-800`, formatting requirements, and an optional full prompt template.

`selected_prompt_preset_id`
: Last selected prompt preset. This is managed by the add-on UI.
