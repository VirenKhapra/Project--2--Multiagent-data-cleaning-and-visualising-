import re
from pathlib import Path

path = Path(r"c:\Users\acer\Documents\agentic_Ai-main\backend\app\api\uploads.py")
content = path.read_text("utf-8")

# Fix the specific syntax errors
content = re.sub(
    r"submission\.summary\.get\('error'\) if isinstance\(submission\.summary, dict\) else None = (.*)",
    r"submission.summary = {'error': \1} if not isinstance(submission.summary, dict) else {**submission.summary, 'error': \1}",
    content
)

path.write_text(content, "utf-8")
print("Fixed syntax errors.")
