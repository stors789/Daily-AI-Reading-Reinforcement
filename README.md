# Daily AI Reading Reinforcement

An Anki add-on that generates a short reading passage from the cards you studied today.

## What It Does

- Adds an `AI Reading Reinforcement` entry inside Anki.
- Uses Anki's own study-day cutoff, so "today" follows Anki's new-day setting.
- Lists decks with cards studied today.
- Shows parent decks as aggregate decks, so a parent can generate from all studied child decks.
- Lets you choose which note fields from each deck are sent to the AI.
- Saves field selections per deck in the Anki add-on config.
- Offers all/invert controls for field selection.
- Lets you save prompt presets for different languages, difficulties, and extra instructions.
- Extracts new cards and failed review cards from the selected deck, with options to "Select All", select "Failed", or select "New" (which add to your selection instead of clearing it).
- Supports intuitive drag-to-select functionality for cards.
- Sends those terms to an OpenAI-compatible API.
- Displays the generated article in a local styled page, featuring a compact UI layout optimized for multiple languages (English, Chinese, Japanese).
- Saves Markdown and HTML copies under the add-on's `user_files/articles` directory.
- Lets you configure common OpenAI-compatible providers inside the add-on page.
- Can optionally create article cards under a `Daily AI Reading Reinforcement` parent deck (newly created cards are set to suspended by default).

## Status

See [TODO.md](TODO.md) for the completed initial roadmap.

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
  "selected_provider_profile": "openai",
  "temperature": 0.7,
  "max_tokens": 30000,
  "prompt_template": "",
  "deck_field_config": {},
  "create_article_cards": false,
  "last_selected_deck_id": "",
  "collapsed_deck_groups": [],
  "ui_language": "zh",
  "prompt_presets": [
    {
      "id": "default",
      "name": "Default",
      "reader_native_language": "",
      "article_language": "",
      "difficulty": "",
      "max_words": "",
      "instructions": "",
      "prompt_template": ""
    }
  ],
  "selected_prompt_preset_id": "default"
}
```

If `prompt_template` is empty, the add-on uses a built-in prompt.

## Package

Run:

```bash
python3 package_addon.py
```

The package will be written to `dist/daily_ai_reading_reinforcement.ankiaddon`.
