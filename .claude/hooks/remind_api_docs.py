"""
PostToolUse hook: reminds Claude to update docs/API_AND_EXTENSION.md
when app/api.py or any extension file is modified.
"""
import json
import re
import sys

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")

if re.search(r"(app/api\.py|extension-chrome/|extension-firefox/)", path):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "You just modified a file that affects the API or extension communication. "
                "Update docs/API_AND_EXTENSION.md to reflect any new endpoints, parameters, "
                "or communication pattern changes."
            ),
        }
    }))
