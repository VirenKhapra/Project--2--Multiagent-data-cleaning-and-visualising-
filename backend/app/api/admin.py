from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.security import require_roles
from app.db.session import get_db
from app.models import AuditAction, RegisteredAgent, ReviewStatus, Submission, User, UserRole
from app.schemas import AdminEmployeeRead, AdminUserRead, AssignmentRequest, QuarantineAssignRequest, UploadSummary
from app.api.uploads import extract_agent_resolution
from app.services.quarantine import is_quarantined_submission, requeue_submission
from app.services.audit import log_action
from app.services.email import send_email

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/managers", response_model=list[AdminUserRead])
async def list_managers(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.admin)),
) -> list[AdminUserRead]:
    employee_alias = aliased(User)
    rows = (
        await db.execute(
            select(User, func.count(employee_alias.id).label("employee_count"))
            .join(employee_alias, employee_alias.manager_id == User.id, isouter=True)
            .where(User.role == UserRole.manager)
            .group_by(User.id)
            .order_by(User.full_name)
        )
    ).all()
    return [
        AdminUserRead(
            id=manager.id,
            name=manager.full_name,
            email=manager.email,
            role=manager.role.value,
            manager_id=manager.manager_id,
            manager_name=None,
            assigned_employee_count=employee_count,
        )
        for manager, employee_count in rows
    ]


@router.get("/employees", response_model=list[AdminEmployeeRead])
async def list_employees(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.admin)),
) -> list[AdminEmployeeRead]:
    employees = (
        await db.execute(
            select(User)
            .options(selectinload(User.manager))
            .where(User.role == UserRole.employee)
            .order_by(User.full_name)
        )
    ).scalars().all()
    return [
        AdminEmployeeRead(
            id=employee.id,
            name=employee.full_name,
            email=employee.email,
            role=employee.role.value,
            manager_id=employee.manager_id,
            manager_name=employee.manager.full_name if employee.manager else None,
            assignment_status="assigned" if employee.manager_id else "unassigned",
        )
        for employee in employees
    ]


@router.post("/assign", response_model=AdminEmployeeRead)
async def assign_employee(
    payload: AssignmentRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.admin)),
) -> AdminEmployeeRead:
    return await save_assignment(payload, db, admin, allow_existing=False)


@router.post("/reassign", response_model=AdminEmployeeRead)
async def reassign_employee(
    payload: AssignmentRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.admin)),
) -> AdminEmployeeRead:
    return await save_assignment(payload, db, admin, allow_existing=True)


@router.get("/quarantined-jobs", response_model=list[UploadSummary])
async def list_quarantined_jobs(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> list[UploadSummary]:
    submissions = (
        await db.execute(
            select(Submission)
            .options(selectinload(Submission.user), selectinload(Submission.review))
            .order_by(Submission.uploaded_at.desc())
        )
    ).scalars().all()

    quarantined = [submission for submission in submissions if is_quarantined_submission(submission)]
    return [
        UploadSummary(
            id=submission.id,
            sub_id=submission.sub_id,
            filename=submission.file_name,
            instruction=submission.instruction,
            output_format=submission.output_format,
            status=str(submission.status.value) if submission.status else "pending",
            version_number=submission.version_number,
            parent_submission_id=submission.parent_submission_id,
            total_rows=0,
            total_columns=0,
            uploader_name=submission.user.full_name if submission.user else None,
            validation_passed=str(submission.status.value) != "failed" if submission.status else True,
            created_at=submission.uploaded_at,
            reviewed_at=submission.completed_at or (submission.review.reviewed_at if submission.review else None),
            **extract_agent_resolution(submission),
        )
        for submission in quarantined
    ]


@router.post("/quarantined-jobs/{upload_id}/retry", response_model=UploadSummary)
async def retry_quarantined_job(
    upload_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> UploadSummary:
    submission = await _get_quarantined_submission(db, upload_id)
    await requeue_submission(db, submission=submission, actor=admin)
    return await _build_quarantined_job_summary(db, submission.id)


@router.post("/quarantined-jobs/{upload_id}/assign", response_model=UploadSummary)
async def assign_quarantined_job(
    upload_id: UUID,
    payload: QuarantineAssignRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> UploadSummary:
    submission = await _get_quarantined_submission(db, upload_id)
    agent = (
        await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.name == payload.preferred_agent_name.strip())
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Registered agent not found")

    await requeue_submission(
        db,
        submission=submission,
        actor=admin,
        preferred_agent_name=agent.name,
    )
    return await _build_quarantined_job_summary(db, submission.id)


async def save_assignment(payload: AssignmentRequest, db: AsyncSession, admin: User, allow_existing: bool) -> AdminEmployeeRead:
    employee = await db.get(User, payload.employee_id)
    manager = await db.get(User, payload.manager_id)
    if not employee or employee.role != UserRole.employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if not manager or manager.role != UserRole.manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    if employee.manager_id and not allow_existing:
        raise HTTPException(status_code=409, detail="Employee is already assigned")

    employee.manager_id = manager.id
    await db.commit()
    await db.refresh(employee, attribute_names=["manager"])
    await log_action(
        db,
        admin,
        AuditAction.user_reassigned if allow_existing else AuditAction.user_assigned,
        target_id=employee.id,
        target_label=employee.full_name,
        detail=f"Manager: {manager.full_name}",
    )

    await send_email(
        employee.email,
        "You have been assigned to a manager",
        f"Hello {employee.full_name},\n\nYou are now assigned to {manager.full_name} for upload review.",
    )

    return AdminEmployeeRead(
        id=employee.id,
        name=employee.full_name,
        email=employee.email,
        role=employee.role.value,
        manager_id=employee.manager_id,
        manager_name=manager.full_name,
        assignment_status="assigned",
    )


async def _get_quarantined_submission(db: AsyncSession, upload_id) -> Submission:
    submission = (
        await db.execute(
            select(Submission)
            .options(selectinload(Submission.user), selectinload(Submission.review))
            .where(Submission.id == upload_id)
        )
    ).scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not is_quarantined_submission(submission):
        raise HTTPException(status_code=409, detail="Submission is not awaiting agent coverage")
    return submission


async def _build_quarantined_job_summary(db: AsyncSession, upload_id) -> UploadSummary:
    submission = (
        await db.execute(
            select(Submission)
            .options(selectinload(Submission.user), selectinload(Submission.review))
            .where(Submission.id == upload_id)
        )
    ).scalar_one()
    return UploadSummary(
        id=submission.id,
        sub_id=submission.sub_id,
        filename=submission.file_name,
        instruction=submission.instruction,
        output_format=submission.output_format,
        status=str(submission.status.value) if submission.status else "pending",
        version_number=submission.version_number,
        parent_submission_id=submission.parent_submission_id,
        total_rows=0,
        total_columns=0,
        uploader_name=submission.user.full_name if submission.user else None,
        validation_passed=str(submission.status.value) != "failed" if submission.status else True,
        created_at=submission.uploaded_at,
        reviewed_at=submission.completed_at or (submission.review.reviewed_at if submission.review else None),
        **extract_agent_resolution(submission),
    )
