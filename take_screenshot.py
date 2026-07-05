from playwright.sync_api import sync_playwright
import json

state = {
    "api_key": "sk-mock-key",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "selected_provider_profile": "openai",
    "temperature": 0.7,
    "max_tokens": 3000,
    "prompt_template": "",
    "ui_language": "zh",
    "prompt_presets": [],
    "selected_prompt_preset_id": "default",
    "create_article_cards": True,
    "candidate_decks": [
        {"id": "1", "name": "JLPT N1 Vocabulary", "card_count": 24},
        {"id": "2", "name": "TOEFL Core Words", "card_count": 15},
        {"id": "3", "name": "Spanish B2", "card_count": 8}
    ],
    "last_selected_deck_id": "1",
    "selected_cards": [1, 2, 3, 4],
    "deck_fields": {
        "1": ["Word", "Reading", "Meaning", "Sentence"],
        "2": ["Vocab", "Definition", "Example"],
        "3": ["Palabra", "Traducción"]
    },
    "deck_field_config": {
        "1": {"Word": True, "Reading": False, "Meaning": False, "Sentence": False},
        "2": {"Vocab": True, "Definition": False, "Example": False},
        "3": {"Palabra": True, "Traducción": False}
    },
    "article": "这是一篇生成的测试文章。\n\n今天我们学习了几个新的单词...",
    "is_generating": False,
    "collapsed_deck_groups": [],
    "cards_data": [
        {"id": 1, "is_new": True, "is_failed": False, "fields": {"Word": "曖昧", "Reading": "あいまい", "Meaning": "ambiguous"}},
        {"id": 2, "is_new": False, "is_failed": True, "fields": {"Word": "矛盾", "Reading": "むじゅん", "Meaning": "contradiction"}},
        {"id": 3, "is_new": True, "is_failed": False, "fields": {"Word": "偶然", "Reading": "ぐうぜん", "Meaning": "coincidence"}},
        {"id": 4, "is_new": False, "is_failed": False, "fields": {"Word": "必然", "Reading": "ひつぜん", "Meaning": "inevitability"}},
        {"id": 5, "is_new": True, "is_failed": False, "fields": {"Word": "典型", "Reading": "てんけい", "Meaning": "typical"}}
    ]
}

mock_script = f"""
window.pycmd = function(cmd) {{
    console.log('pycmd:', cmd);
    return null;
}};
window.mockState = {json.dumps(state)};
// Override DOMContentLoaded or inject after to ensure state is ready
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_viewport_size({"width": 1000, "height": 800})
    
    # We need to make sure app.js gets the mock state instead of calling pycmd("getState")
    # Actually, in app.js:
    # function requestState() { pycmd("getState"); }
    # So if we override pycmd to immediately call updateState if cmd === 'getState'
    
    mock_script = f"""
    window.pycmd = function(cmd) {{
        if (cmd === 'getState') {{
            setTimeout(() => {{
                updateState({json.dumps(state)});
            }}, 100);
        }}
    }};
    """
    
    page.add_init_script(mock_script)
    
    file_path = "file:///Users/eros/Documents/Daily AI Reading Reinforcement/addon/daily_ai_reading_reinforcement/web/index.html"
    page.goto(file_path)
    page.wait_for_timeout(2000)
    page.screenshot(path="interface_screenshot.png")
    browser.close()
