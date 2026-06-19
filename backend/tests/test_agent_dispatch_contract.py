import ast
import asyncio
from pathlib import Path
from uuid import uuid4

from app.models import Submission, SubmissionStatus
from app.services import agent_dispatcher


class FakeRedis:
    def __init__(self):
        self.jobs: list[tuple[str, dict]] = []

    async def enqueue_job(self, job_name: str, payload: dict) -> None:
        self.jobs.append((job_name, payload))


class FakeDbSession:
    def __init__(self, submission: Submission):
        self.submission = submission
        self.committed = False

    async def get(self, model, submission_id):
        assert model is Submission
        assert str(submission_id) == str(self.submission.id)
        return self.submission

    async def commit(self):
        self.committed = True


class FakeSessionManager:
    def __init__(self, session: FakeDbSession):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _agent_service_job_payload_fields() -> list[str]:
    source = (_repo_root() / "agent-framework" / "new-agentic-project-data-cleaning-" / "src" / "finflow_agent" / "api.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "JobPayload":
            fields: list[str] = []
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.append(stmt.target.id)
            return fields
    raise AssertionError("JobPayload class was not found in the agent service API")


def test_agent_dispatcher_sends_file_id_not_file_path(monkeypatch, tmp_path):
    async def run() -> tuple[str, dict, bool, str, str]:
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        stored_file = upload_dir / "stored-input.csv"
        stored_file.write_text("a,b\n1,2\n", encoding="utf-8")

        submission = Submission(
            id=uuid4(),
            file_name="original-input.csv",
            file_path=str(stored_file),
            file_size_bytes=10,
            original_filename="original-input.csv",
            instruction="clean this",
            output_format="XLSX",
            user_id=uuid4(),
            version_number=1,
            status=SubmissionStatus.queued,
        )

        fake_redis = FakeRedis()
        fake_db = FakeDbSession(submission)

        async def fake_create_pool(*_args, **_kwargs):
            return fake_redis

        monkeypatch.setattr(agent_dispatcher, "create_pool", fake_create_pool)
        monkeypatch.setattr(agent_dispatcher, "AsyncSessionLocal", lambda: FakeSessionManager(fake_db))
        monkeypatch.setattr(
            agent_dispatcher,
            "get_settings",
            lambda: type("Settings", (), {"redis_url": "redis://localhost:6379/0"})(),
        )

        await agent_dispatcher.enqueue_submission_dispatch(submission.id)
        assert fake_redis.jobs
        job_name, payload = fake_redis.jobs[0]
        return job_name, payload, fake_db.committed, submission.status.value, str(submission.id)

    job_name, payload, committed, status, submission_id = asyncio.run(run())

    assert job_name == "process_job_task"
    assert payload == {
        "submission_id": submission_id,
        "file_id": "stored-input.csv",
        "file_name": "original-input.csv",
        "instruction": "clean this",
        "output_format": "xlsx",
    }
    assert "file_path" not in payload
    assert committed is True
    assert status == SubmissionStatus.planning.value


def test_agent_payload_matches_agent_service_job_payload(monkeypatch, tmp_path):
    async def run() -> dict:
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        stored_file = upload_dir / "job-input.csv"
        stored_file.write_text("a,b\n1,2\n", encoding="utf-8")

        submission = Submission(
            id=uuid4(),
            file_name="job-input.csv",
            file_path=str(stored_file),
            file_size_bytes=10,
            original_filename="job-input.csv",
            instruction="normalize values",
            output_format="CSV",
            user_id=uuid4(),
            version_number=1,
            status=SubmissionStatus.queued,
        )

        fake_redis = FakeRedis()
        fake_db = FakeDbSession(submission)

        async def fake_create_pool(*_args, **_kwargs):
            return fake_redis

        monkeypatch.setattr(agent_dispatcher, "create_pool", fake_create_pool)
        monkeypatch.setattr(agent_dispatcher, "AsyncSessionLocal", lambda: FakeSessionManager(fake_db))
        monkeypatch.setattr(
            agent_dispatcher,
            "get_settings",
            lambda: type("Settings", (), {"redis_url": "redis://localhost:6379/0"})(),
        )

        await agent_dispatcher.enqueue_submission_dispatch(submission.id)
        return fake_redis.jobs[0][1]

    payload = asyncio.run(run())
    agent_fields = _agent_service_job_payload_fields()

    assert sorted(payload.keys()) == sorted(agent_fields)
    assert "file_path" not in payload
    assert payload["file_id"] == "job-input.csv"
    assert payload["output_format"] == "csv"
    assert agent_fields == [
        "submission_id",
        "file_id",
        "file_name",
        "instruction",
        "output_format",
    ]


def test_shared_upload_dir_contract_documented():
    compose_text = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")
    deploy_text = (_repo_root() / "docs" / "RAILWAY_DEPLOYMENT.md").read_text(encoding="utf-8")

    assert compose_text.count("UPLOAD_DIR: /app/storage/uploads") >= 2
    assert "backend_storage:/app/storage" in compose_text
    assert "UPLOAD_DIR=/app/storage/uploads" in deploy_text
