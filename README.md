# Daily AI Reading Reinforcement

An Anki add-on that generates a short reading passage from the cards you studied today.

## What It Does

- Adds an `AI Reading Reinforcement` entry inside Anki.
- Uses Anki's own study-day cutoff, so "today" follows Anki's new-day setting.
- Lists decks with cards studied today.
- Extracts new cards and failed review cards from the selected deck.
- Sends those terms to an OpenAI-compatible API.
- Displays the generated article in a local styled page.
- Saves Markdown and HTML copies under the add-on's `user_files/articles` directory.

## Layout

```text
addon/daily_ai_reading_reinforcement/
  __init__.py
  config.json
  manifest.json
  web/
    app.js
    index.html
    style.css
```

## Install for Development

Copy or symlink `addon/daily_ai_reading_reinforcement` into your Anki add-ons directory, then restart Anki.

On macOS, the target is usually:

```text
~/Library/Application Support/Anki2/addons21/daily_ai_reading_reinforcement
```

Then open Anki, find the add-on config, and set your API key.

## Config

The add-on uses an OpenAI-compatible chat completions API:

```json
{
  "api_key": "",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4.1-mini",
  "temperature": 0.7,
  "max_tokens": 1400,
  "language": "English",
  "prompt_template": ""
}
```

If `prompt_template` is empty, the add-on uses a built-in prompt.

## Package

Run:

```bash
python3 package_addon.py
```

The package will be written to `dist/daily_ai_reading_reinforcement.ankiaddon`.
