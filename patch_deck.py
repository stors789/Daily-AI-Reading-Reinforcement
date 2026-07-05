import re

with open("addon/daily_ai_reading_reinforcement/web/app.js", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('selectDeckShort: "选择卡组",', 'selectDeckShort: "",')
content = content.replace('selectDeckShort: "Select a deck",', 'selectDeckShort: "",')
content = content.replace('selectDeckShort: "デッキを選択",', 'selectDeckShort: "",')

with open("addon/daily_ai_reading_reinforcement/web/app.js", "w", encoding="utf-8") as f:
    f.write(content)
