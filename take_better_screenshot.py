from playwright.sync_api import sync_playwright
import json
import os

state = {
    "api_key": "sk-mock-key",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "selected_provider_profile": "openai",
    "temperature": 0.7,
    "max_tokens": 3000,
    "prompt_template": "",
    "ui_language": "zh",
    "prompt_presets": [
        {"id": "default", "name": "Default"}
    ],
    "selected_prompt_preset_id": "default",
    "create_article_cards": True,
    "candidate_decks": [
        {"id": "1", "name": "eggrolls-JLPT10k-v3", "card_count": 6}
    ],
    "last_selected_deck_id": "1",
    "selected_cards": [1, 2, 3, 4],
    "deck_fields": {
        "1": ["NoteID", "VocabKanji", "VocabPitch", "VocabPoS", "VocabFurigana", "VocabDefSC"]
    },
    "deck_field_config": {
        "1": {"NoteID": True, "VocabKanji": True, "VocabPitch": True, "VocabPoS": True, "VocabFurigana": True, "VocabDefSC": True}
    },
    "article": "在这篇文章中，我们将学习几个日语单词...",
    "is_generating": False,
    "collapsed_deck_groups": [],
    "cards_data": [
        {
            "id": 1, "is_new": False, "is_failed": True, 
            "fields": {"VocabKanji": "引き上げる", "VocabPitch": "④"}
        },
        {
            "id": 2, "is_new": False, "is_failed": True, 
            "fields": {"VocabKanji": "はしゃぐ", "VocabPitch": "②③"}
        },
        {
            "id": 3, "is_new": False, "is_failed": True, 
            "fields": {"VocabKanji": "即刻", "VocabPitch": "⓪"}
        },
        {
            "id": 4, "is_new": False, "is_failed": True, 
            "fields": {"VocabKanji": "強硬", "VocabPitch": "⓪"}
        }
    ]
}

html_file = "/Users/eros/Documents/Daily AI Reading Reinforcement/addon/daily_ai_reading_reinforcement/web/index.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1400, "height": 900},
        device_scale_factor=2
    )
    page = context.new_page()
    
    font_injection = """
    const link = document.createElement('link');
    link.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
    
    const style = document.createElement('style');
    style.innerHTML = `
        :root {
            --font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }
        body { font-family: var(--font-family); background: #fdfbf7; }
        ::-webkit-scrollbar { display: none; }
    `;
    document.head.appendChild(style);
    """
    
    mock_script = f"""
    window.pycmd = function(cmd) {{
        if (cmd === 'getState') {{
            setTimeout(() => {{
                updateState({json.dumps(state)});
            }}, 50);
        }}
    }};
    """
    
    page.add_init_script(mock_script)
    page.goto(f"file://{html_file}")
    
    page.evaluate(font_injection)
    page.wait_for_timeout(2000)
    
    # Just screenshot the body to get the full view safely
    page.locator('body').screenshot(path="screenshot.png")
    browser.close()
