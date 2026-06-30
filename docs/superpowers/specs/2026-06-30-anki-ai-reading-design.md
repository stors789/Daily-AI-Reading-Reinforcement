# Anki AI Reading Reinforcement Design

## Goal

Build an Anki add-on that turns the cards studied today into a short AI-generated reading passage for reinforcement. The add-on should live inside Anki, open from the main window, let the user pick a deck studied today, generate a passage from that deck's new and failed cards, display the passage in a polished local page, and save the result for later review.

## Scope

The first version is a manual workflow:

1. The user opens the add-on from Anki.
2. The add-on lists decks with learning activity in Anki's current study day.
3. The user selects one deck.
4. The add-on shows candidate cards from that deck.
5. The user clicks Generate.
6. The add-on sends a prompt to an OpenAI-compatible API.
7. The returned article is displayed in the add-on page.
8. Markdown and HTML copies are saved under the add-on's `user_files/articles` directory.

The first version will not auto-run every day, create Anki cards from the generated article, or manage multiple prompt templates in the UI.

## Date Window

The add-on uses Anki's scheduler day boundary rather than calendar midnight. It reads the collection scheduler cutoff and treats today's learning window as:

`[day_cutoff - 86400, day_cutoff)`

This follows the user's Anki setting for when a new day starts. In the common default configuration, the new day begins at 4 AM.

## Data Extraction

The add-on reads `revlog` entries inside today's Anki day window, joins them to cards and notes, and groups activity by deck. Each deck summary contains:

- new cards studied today
- failed cards reviewed today, identified by `ease == 1`
- all candidate notes for prompt input

For card text, the first note field is used as the main term. Other fields are retained as supporting context where available.

## UI

The add-on opens a dialog containing a local Anki WebView. All HTML, CSS, and JavaScript are bundled inside the add-on. No CDN or external web assets are required.

The page has three work areas:

- deck list for decks studied today
- card preview for the selected deck
- article panel for generation status and the final reading passage

The visual style should feel like a focused reading workspace: clear typography, calm colors, and enough layout polish that the AI result can be read directly inside Anki.

## AI Integration

The add-on uses an OpenAI-compatible chat completions endpoint configured through Anki add-on config:

- `api_key`
- `base_url`
- `model`
- `temperature`
- `max_tokens`
- `language`
- `prompt_template`

The request is made with Python's standard library so the add-on does not require dependency installation.

## Saving

Generated articles are saved in the add-on's user files directory:

- `articles/YYYY-MM-DD-deck-slug-HHMMSS.md`
- `articles/YYYY-MM-DD-deck-slug-HHMMSS.html`

The Markdown file stores the source article and metadata. The HTML file stores a styled standalone reading page.

## Error Handling

The UI should show clear messages when:

- no collection is open
- no decks were studied today
- a deck has no candidate cards
- the API key is missing
- the AI request fails
- the response is empty
- the article cannot be saved

## Testing

Because Anki APIs are only available inside Anki, local verification focuses on syntax checks and packaging sanity. Runtime verification should be done by copying or symlinking the add-on folder into Anki's add-ons directory, setting the API key in Anki's add-on config, restarting Anki, and trying the manual workflow on a profile with today's review history.
