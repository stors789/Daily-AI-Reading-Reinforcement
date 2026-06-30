# Daily AI Reading Reinforcement Config

`api_key`
: Your OpenAI-compatible API key.

`base_url`
: API base URL. For OpenAI, use `https://api.openai.com/v1`.

`model`
: Chat completions model name.

`temperature`
: Sampling temperature for the generated article.

`max_tokens`
: Maximum tokens for the AI response.

`language`
: Target language for the article, such as `English` or `中文`.

`prompt_template`
: Optional custom prompt. You can use `{language}`, `{deck_name}`, and `{cards}` placeholders.

`deck_field_config`
: Saved field selections for each deck. This is managed by the add-on UI.

`prompt_presets`
: Saved prompt presets. Each preset can define language, difficulty, extra instructions, and an optional full prompt template.

`selected_prompt_preset_id`
: Last selected prompt preset. This is managed by the add-on UI.
