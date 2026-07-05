import re

with open("addon/daily_ai_reading_reinforcement/web/app.js", "r", encoding="utf-8") as f:
    content = f.read()

# Add dayStart and dayEnd to state
content = re.sub(
    r"    readingMode: false,\n  \};\n",
    "    readingMode: false,\n    dayStart: 0,\n    dayEnd: 0,\n  };\n",
    content
)

# Save to state in receive
content = content.replace(
    "        el.dayWindow.textContent = `${formatTime(payload.dayStart)} - ${formatTime(payload.dayEnd)}`;\n",
    """        state.dayStart = payload.dayStart;
        state.dayEnd = payload.dayEnd;
        el.dayWindow.textContent = `${formatTime(state.dayStart)} - ${formatTime(state.dayEnd)}`;\n"""
)

# Update dayWindow in applyI18n
content = content.replace(
    "    if (state.decks.length) renderDecks();",
    """    if (state.dayStart && state.dayEnd) {
      el.dayWindow.textContent = `${formatTime(state.dayStart)} - ${formatTime(state.dayEnd)}`;
    }
    if (state.decks.length) renderDecks();"""
)

with open("addon/daily_ai_reading_reinforcement/web/app.js", "w", encoding="utf-8") as f:
    f.write(content)
