from app.agent_client import _candidate_agent_base_urls


def test_candidate_agent_base_urls_falls_back_from_container_host():
    assert _candidate_agent_base_urls("http://agent-service:8001") == [
        "http://agent-service:8001",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
    ]


def test_candidate_agent_base_urls_falls_back_from_localhost():
    assert _candidate_agent_base_urls("http://localhost:8001") == [
        "http://localhost:8001",
        "http://agent-service:8001",
    ]
