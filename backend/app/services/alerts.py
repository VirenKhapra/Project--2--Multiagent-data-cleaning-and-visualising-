from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Submission, User, UserRole
from app.schemas import AlertRead
from app.services.email import send_email
from app.services.websocket_manager import ws_manager


def format_display_job_id(sub_id: int | None, submission_id) -> str:
    if sub_id:
        return f"FF-{str(sub_id).zfill(5)}"
    return f"FF-{str(submission_id).replace('-', '')[:8].upper()}"


def alert_to_payload(alert: AlertRead) -> dict:
    return alert.model_dump(mode="json")


async def build_alert_read(alert: Alert) -> AlertRead:
    return AlertRead(
        id=alert.id,
        alert_type=alert.alert_type,
        title=alert.title,
        message=alert.message,
        upload_id=alert.upload_id,
        entry_no=alert.entry_no,
        account_code=alert.account_code,
        sub_account=alert.sub_account,
        difference=float(alert.difference),
        status=alert.status,
        is_read=alert.is_read,
        created_at=alert.created_at,
    )


async def create_quarantine_alert(
    db: AsyncSession,
    *,
    submission: Submission,
    reason: str,
    suggestion: str,
) -> AlertRead:
    title = f"Workflow {format_display_job_id(submission.sub_id, submission.id)} is awaiting a capable agent"
    message = suggestion or "Manual review is required before this workflow can continue."
    alert = (
        await db.execute(
            select(Alert)
            .where(Alert.upload_id == submission.id, Alert.alert_type == "workflow_quarantine")
            .order_by(desc(Alert.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    if alert is None:
        alert = Alert(
            alert_type="workflow_quarantine",
            title=title,
            message=message,
            upload_id=submission.id,
            entry_no=format_display_job_id(submission.sub_id, submission.id),
            account_code="NO_CAPABLE_AGENT",
            sub_account=submission.file_name,
            difference=0,
            status="QUARANTINED",
        )
        db.add(alert)
    else:
        alert.title = title
        alert.message = message
        alert.entry_no = format_display_job_id(submission.sub_id, submission.id)
        alert.account_code = "NO_CAPABLE_AGENT"
        alert.sub_account = submission.file_name
        alert.status = "QUARANTINED"
        alert.is_read = False

    await db.commit()
    await db.refresh(alert)

    alert_schema = await build_alert_read(alert)
    payload = alert_to_payload(alert_schema)
    await ws_manager.broadcast("dashboard", "workflow_alert", payload)
    await ws_manager.broadcast("notifications", "workflow_alert", payload)
    await ws_manager.broadcast("manager", "workflow_alert", payload)

    await notify_quarantine_recipients(db, submission=submission, reason=reason, suggestion=suggestion)
    return alert_schema


async def notify_quarantine_recipients(
    db: AsyncSession,
    *,
    submission: Submission,
    reason: str,
    suggestion: str,
) -> None:
    recipients: dict[str, User] = {}

    if submission.user and submission.user.manager_id:
        manager = await db.get(User, submission.user.manager_id)
        if manager:
            recipients[str(manager.id)] = manager
    else:
        managers = (
            await db.execute(select(User).where(User.role == UserRole.manager))
        ).scalars().all()
        for manager in managers:
            recipients[str(manager.id)] = manager

    admins = (
        await db.execute(select(User).where(User.role == UserRole.admin))
    ).scalars().all()
    for admin in admins:
        recipients[str(admin.id)] = admin

    display_job_id = format_display_job_id(submission.sub_id, submission.id)
    for recipient in recipients.values():
        await send_email(
            recipient.email,
            f"Workflow {display_job_id} requires agent coverage",
            (
                f"Hello {recipient.full_name},\n\n"
                f"{submission.file_name} was quarantined because part of the workflow could not continue.\n\n"
                f"Reason: {reason or 'No capable agent matched the workflow requirements.'}\n"
                f"Next step: {suggestion or 'Review the workflow and add or assign an appropriate agent.'}\n\n"
                f"Open FinFlow to review workflow {display_job_id}."
            ),
        )
