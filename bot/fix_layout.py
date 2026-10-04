import re

path = r"C:\Users\olivi\.gemini\antigravity\scratch\betdice\bot\main.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

clean_layout = """LAYOUT = {
    "important": [
        ("ticket", False),
        ("news", True),
        ("invite-rewards", False),
        ("event", False),
        ("giveaway", False),
        ("invite", False),
    ],
    "PLAY": [
        ("history", True),
        ("play-1", False),
        ("play-2", False),
        ("play-3", False),
    ],
    "COMMUNITY": [
        ("general", False),
        ("vouch", False),
    ],
}"""

text = re.sub(r'LAYOUT = \{[\s\S]*?\n\}', clean_layout, text, count=1)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("Layout successfully cleaned!")
