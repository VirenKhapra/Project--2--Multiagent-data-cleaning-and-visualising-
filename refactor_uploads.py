import re
from pathlib import Path

path = Path(r"c:\Users\acer\Documents\agentic_Ai-main\backend\app\api\uploads.py")
content = path.read_text("utf-8")

# Replacements
replacements = [
    (r"submission\.review_status\.value", r"submission.status"),
    (r"submission\.review_status == ReviewStatus\.pending", r"submission.status == 'pending'"),
    (r"submission\.review_status == ReviewStatus\.processing", r"submission.status == 'processing'"),
    (r"submission\.review_status == ReviewStatus\.complete", r"submission.status == 'complete'"),
    (r"submission\.review_status == ReviewStatus\.failed", r"submission.status == 'failed'"),
    (r"submission\.review_status != ReviewStatus\.complete", r"submission.status != 'complete'"),
    (r"submission\.review_status != ReviewStatus\.failed", r"submission.status != 'failed'"),
    (r"submission\.review_status in \{ReviewStatus\.complete, ReviewStatus\.failed\}", r"submission.status in {'complete', 'failed'}"),
    (r"submission\.review_status not in \{ReviewStatus\.failed, ReviewStatus\.complete\}", r"submission.status not in {'failed', 'complete'}"),
    (r"submission\.review_status = ReviewStatus\.processing", r"submission.status = 'processing'"),
    (r"submission\.review_status = ReviewStatus\.complete", r"submission.status = 'complete'"),
    (r"submission\.review_status = ReviewStatus\.failed", r"submission.status = 'failed'"),
    (r"submission\.review_status = ReviewStatus\.pending", r"submission.status = 'pending'"),
    (r"submission\.agent_status", r"submission.status"),
    (r"submission\.agent_result", r"submission.summary"),
    (r"submission\.agent_error", r"submission.summary.get('error') if isinstance(submission.summary, dict) else None"),
    (r"submission\.output_file_path", r"submission.output_path"),
    (r"ReviewStatus\(normalized_status\)", r"normalized_status"),
    (r"Submission\.review_status == ReviewStatus\(normalized_status\)", r"Submission.status == normalized_status"),
    (r"Submission\.review_status == ReviewStatus\.pending", r"Submission.status == 'pending'"),
    (r"Submission\.review_status", r"Submission.status"),
    (r"version\.review_status\.value", r"version.status"),
    (r"refreshed\.review_status\.value", r"refreshed.status")
]

for old, new in replacements:
    content = re.sub(old, new, content)

# A few specific fixes:
content = content.replace("from app.models import AuditLog, Review, ReviewStatus, Submission, SubmissionRecord, User, UserRole", "from app.models import AuditLog, Review, Submission, SubmissionRecord, User, UserRole")
content = content.replace("Submission.agent_result[\"status\"].astext", "Submission.summary[\"status\"].astext")

path.write_text(content, "utf-8")
print("Refactored uploads.py")
