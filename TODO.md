# TODO

## Localization

- Fix language switching so every visible UI string updates immediately, including status text, empty states, card tags, tooltips, and "Select a deck" style placeholders.
- Store UI state as keys plus parameters where possible instead of storing already-translated status strings.

## Provider Profiles

- Expand provider presets only after checking each provider's official API documentation during implementation.
- For each provider profile, record the official docs URL, verified date, base URL, chat completions path, default model, auth notes, and any compatibility caveats.
- Keep a custom OpenAI-compatible option for providers that are not in the preset list.

## Prompt And Language Boundaries

- Replace the single `language` preset field with separate reader native language and article language fields.
- Do not standardize or enumerate article languages; accept free-form languages such as Japanese, German, French, Arabic, or user-specific wording.
- Make the prompt enforce format and language boundaries only, not story topic, scenario, tone, or content direction.
- Require the main article to use only the article language, while review notes may use the reader native language.
- Ensure source fields in the reader's native language are treated as meaning/context and do not leak into the main article unless explicitly required as source terms.
- Rename or clarify the extra instructions field as formatting requirements so it does not imply content direction.

## Reading Experience

- Make the generated article the primary post-generation view instead of confining it to a narrow right-side panel.
- Add a reading mode where the article uses a comfortable reading width and the deck, field, provider, and preset controls collapse or move aside.
- Keep regenerate, return to selection, saved paths, and article-card status accessible without stealing the main reading area.
