"""Tests for the LLM/provider boundary role normalization.

Locks the contract from the production failure:

    HTTP 400 - 'messages.1' : discriminator property 'role' has invalid value

Root cause: ``planning.orchestrator.Orchestrator.build_plan`` constructs
provider payloads via
``[{"role": m.type, "content": m.content} for m in prompt.format_messages()]``,
and LangChain's ``HumanMessage.type == "human"`` (not ``"user"``). Groq's
chat API rejects ``human`` because its ``role`` field is a closed
discriminator over ``{system, user, assistant, tool}``.

Fix: ``finflow_agent.llm.normalize_outbound_messages`` translates
framework roles to provider wire roles at the single LLM/provider
boundary. Both ``call_groq_json`` (raw client) and the orchestrator's
``USE_STRUCTURED_LLM`` path route through it.

These tests assert:

1. The normalizer maps every supported role correctly.
2. Unknown roles fail fast with a clear ``ValueError`` (NOT a silent
   pass-through, NOT a quarantine masquerade).
3. The Groq client receives only wire-format roles after the boundary
   runs (regression test for the original 400).
4. The orchestrator no longer 400s on ``human`` roles end-to-end (the
   exact failure shape from the production callback log).
5. The existing test seam — monkeypatching
   ``finflow_agent.orchestrator.call_groq_json`` — still works.

All tests are deterministic. None of them call a real Groq endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest


# ---------------------------------------------------------------------------
# 1. Direct unit tests for ``normalize_outbound_messages``
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "internal_role, provider_role",
    [
        ("human", "user"),
        ("ai", "assistant"),
        ("system", "system"),
        ("user", "user"),
        ("assistant", "assistant"),
        ("tool", "tool"),
    ],
)
def test_normalize_maps_internal_role_to_provider_role(
    internal_role: str, provider_role: str
):
    """Every supported internal/framework role maps to the right wire role.

    Locks the boundary translation table. ``HumanMessage.type=='human'``
    must surface as ``role='user'`` on the wire; ``AIMessage.type=='ai'``
    must surface as ``role='assistant'``; the wire roles themselves pass
    through unchanged.
    """
    from finflow_agent.llm import normalize_outbound_messages

    normalized = normalize_outbound_messages(
        [{"role": internal_role, "content": "hello"}]
    )

    assert len(normalized) == 1
    assert normalized[0] == {"role": provider_role, "content": "hello"}


def test_normalize_is_case_insensitive_and_trims_whitespace():
    """``"Human"``, ``"  AI "``, ``"SYSTEM"`` all normalize correctly.

    Operators sometimes hand-craft messages with mixed case; the boundary
    treats them identically to canonical lowercase tokens.
    """
    from finflow_agent.llm import normalize_outbound_messages

    normalized = normalize_outbound_messages(
        [
            {"role": "Human", "content": "h"},
            {"role": "  AI ", "content": "a"},
            {"role": "SYSTEM", "content": "s"},
        ]
    )

    assert [m["role"] for m in normalized] == ["user", "assistant", "system"]


def test_normalize_returns_a_new_list_and_does_not_mutate_input():
    """The boundary must not mutate caller-owned data."""
    from finflow_agent.llm import normalize_outbound_messages

    original = [{"role": "human", "content": "hello"}]
    snapshot = [dict(m) for m in original]

    normalized = normalize_outbound_messages(original)

    assert normalized is not original
    assert original == snapshot, (
        "normalize_outbound_messages must not mutate its input list/dicts."
    )


def test_normalize_preserves_message_order_and_count():
    """A 3-message conversation comes out as a 3-message conversation in
    the same order."""
    from finflow_agent.llm import normalize_outbound_messages

    normalized = normalize_outbound_messages(
        [
            {"role": "system", "content": "sys"},
            {"role": "human", "content": "user msg"},
            {"role": "ai", "content": "assistant reply"},
        ]
    )

    assert [m["role"] for m in normalized] == ["system", "user", "assistant"]
    assert [m["content"] for m in normalized] == ["sys", "user msg", "assistant reply"]


def test_normalize_strict_payload_shape_only_role_and_content():
    """Output dicts have exactly ``role`` and ``content``; nothing else.

    The Groq API rejects extra keys, and the structural ``assert_no_eval_strings``
    check immediately downstream relies on this strict shape.
    """
    from finflow_agent.llm import normalize_outbound_messages

    normalized = normalize_outbound_messages(
        [{"role": "human", "content": "hi"}]
    )

    assert set(normalized[0].keys()) == {"role", "content"}


# ---------------------------------------------------------------------------
# 2. Fail-fast: unknown roles raise ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_role",
    [
        "agent",         # plausible-looking but unknown
        "function",      # OpenAI's old role; not supported here
        "developer",     # OpenAI o-series role; not supported here
        "banana",        # nonsense
        "User1",         # accidentally numbered
        "human ",        # trailing space without normalize would fail
    ],
)
def test_normalize_rejects_unknown_role(bad_role: str):
    """Unknown roles MUST fail fast with a ``ValueError`` — never silently
    coerce, never default. The error must name the offending role and
    list the closed allow-set so the operator can fix the call site.

    The single exception in this list is ``"human "`` (trailing space).
    The normalizer trims internal whitespace by design, so that string
    actually maps to ``user`` and would NOT raise. We exercise it
    elsewhere; this parametrization is for genuinely unknown tokens.
    """
    if bad_role.strip().lower() in {"human", "ai", "system", "user", "assistant", "tool"}:
        pytest.skip(f"{bad_role!r} normalizes successfully after trim/lower.")

    from finflow_agent.llm import normalize_outbound_messages

    with pytest.raises(ValueError) as excinfo:
        normalize_outbound_messages([{"role": bad_role, "content": "hi"}])

    msg = str(excinfo.value)
    assert "messages[0]" in msg
    assert bad_role in msg or bad_role.lower() in msg
    # Must enumerate the allow-set so a human reading the error knows
    # exactly which roles are valid.
    for allowed in ("system", "user", "assistant", "tool"):
        assert allowed in msg, (
            f"error message must enumerate allowed role {allowed!r}; got: {msg!r}"
        )


def test_normalize_rejects_non_list_input():
    from finflow_agent.llm import normalize_outbound_messages

    with pytest.raises(ValueError, match="messages must be a list"):
        normalize_outbound_messages({"role": "human", "content": "hi"})


def test_normalize_rejects_non_dict_message():
    from finflow_agent.llm import normalize_outbound_messages

    with pytest.raises(ValueError, match=r"messages\[0\] must be a dict"):
        normalize_outbound_messages(["just a string"])


def test_normalize_rejects_message_missing_role():
    from finflow_agent.llm import normalize_outbound_messages

    with pytest.raises(ValueError, match=r"missing required key 'role'"):
        normalize_outbound_messages([{"content": "no role here"}])


def test_normalize_rejects_empty_role_string():
    from finflow_agent.llm import normalize_outbound_messages

    with pytest.raises(ValueError, match="role must be a non-empty string"):
        normalize_outbound_messages([{"role": "", "content": "hi"}])


def test_normalize_rejects_non_string_role():
    from finflow_agent.llm import normalize_outbound_messages

    with pytest.raises(ValueError, match="role must be a non-empty string"):
        normalize_outbound_messages([{"role": 42, "content": "hi"}])


# ---------------------------------------------------------------------------
# 3. Regression: ``call_groq_json`` actually translates roles before sending
# ---------------------------------------------------------------------------


class _FakeChatCompletions:
    """Minimal stand-in for ``Groq().chat.completions``.

    Captures every ``create(...)`` call so the test can assert on the
    exact ``messages`` payload the boundary handed to the provider client.
    """

    def __init__(self, response_content: str = '{"is_quarantined": false}') -> None:
        self.calls: List[Dict[str, Any]] = []
        self._response_content = response_content

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)

        # Build a minimal duck-typed response that ``call_groq_json``'s
        # final ``json.loads(chat_completion.choices[0].message.content)``
        # call walks without complaint.
        class _Msg:
            content = self._response_content

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


class _FakeGroqClient:
    def __init__(self, response_content: str = '{"is_quarantined": false}') -> None:
        self.chat = type("_Chat", (), {})()
        self.chat.completions = _FakeChatCompletions(response_content)


def test_call_groq_json_normalizes_human_role_before_sending(monkeypatch):
    """The exact regression: a ``human`` role from a LangChain template
    becomes ``user`` on the wire. This is what the production 400
    failure was telling us.
    """
    from finflow_agent import llm

    fake_client = _FakeGroqClient()
    monkeypatch.setattr(llm, "get_groq_client", lambda: fake_client)

    payload = [
        {"role": "system", "content": "you are a planner"},
        {"role": "human", "content": "make me a csv report"},
    ]

    result = llm.call_groq_json(payload, schema={})

    # Groq returned a successful empty PlanIntent shape.
    assert result == {"is_quarantined": False}

    # The boundary handed Groq a payload with ZERO framework roles.
    assert len(fake_client.chat.completions.calls) == 1
    sent_messages = fake_client.chat.completions.calls[0]["messages"]

    sent_roles = [m["role"] for m in sent_messages]
    assert sent_roles == ["system", "user"], (
        f"call_groq_json must translate 'human' -> 'user' before the "
        f"network round trip; payload sent was {sent_messages!r}"
    )

    # Defense-in-depth: nothing in the wire payload still uses internal
    # framework role tokens.
    for msg in sent_messages:
        assert msg["role"] not in {"human", "ai"}, (
            f"framework role leaked to provider payload: {msg!r}"
        )


def test_call_groq_json_preserves_content_through_the_boundary(monkeypatch):
    from finflow_agent import llm

    fake_client = _FakeGroqClient()
    monkeypatch.setattr(llm, "get_groq_client", lambda: fake_client)

    payload = [
        {"role": "system", "content": "S"},
        {"role": "human", "content": "H content here"},
        {"role": "ai", "content": "A content here"},
    ]
    llm.call_groq_json(payload, schema={})

    sent = fake_client.chat.completions.calls[0]["messages"]
    assert [m["content"] for m in sent] == ["S", "H content here", "A content here"]


def test_call_groq_json_fails_fast_on_unknown_role(monkeypatch):
    """An unknown role must surface as a clean ``ValueError`` BEFORE any
    network request is issued. We assert no Groq client is even
    instantiated by the time the error is raised.
    """
    from finflow_agent import llm

    instantiated: List[bool] = []

    def _trip_wire():
        instantiated.append(True)
        raise AssertionError(
            "get_groq_client must not be called when normalization fails."
        )

    monkeypatch.setattr(llm, "get_groq_client", _trip_wire)

    with pytest.raises(ValueError):
        llm.call_groq_json(
            [{"role": "agent", "content": "hi"}], schema={}
        )

    assert instantiated == [], (
        "Normalizer must reject unknown roles before any provider call."
    )


# ---------------------------------------------------------------------------
# 4. Planner regression: ``Orchestrator.build_plan`` no longer 400s on
#    ``human`` roles. Uses the existing ``call_groq_json`` test seam so the
#    fix is exercised end-to-end through the orchestrator.
# ---------------------------------------------------------------------------


def test_orchestrator_succeeds_when_template_emits_human_role(
    monkeypatch, bootstrap_agents, tmp_path
):
    """End-to-end: the planner builds messages with LangChain (which emits
    ``human``), the LLM call goes through ``call_groq_json``, and the
    orchestrator returns a valid ``ExecutionPlan`` — not a quarantine
    dict carrying the 400 discriminator error.

    This is the regression test for the production failure:
        HTTP 400 - 'messages.1' : discriminator property 'role' has
        invalid value

    The test seam (monkeypatching ``finflow_agent.orchestrator.call_groq_json``)
    is preserved; we capture the messages it receives and assert they
    have already been translated to wire-format roles.
    """
    from finflow_agent.planning.orchestrator import Orchestrator
    from finflow_agent.state import ExecutionPlan

    captured_messages: List[List[Dict[str, str]]] = []

    def fake_call_groq_json(messages: list, schema: dict) -> dict:
        captured_messages.append(messages)
        return {
            "is_quarantined": False,
            "needs_cleaning": False,
            "needs_filtering": False,
            "needs_calculation": False,
            "needs_visualization": False,
            "output_format": "csv",
        }

    import finflow_agent.orchestrator as root_orchestrator

    monkeypatch.setattr(root_orchestrator, "call_groq_json", fake_call_groq_json)

    csv_path = tmp_path / "input.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    result = Orchestrator().build_plan(
        instruction="make a csv report",
        file_path=str(csv_path),
        file_name="input.csv",
        output_format="csv",
    )

    # The orchestrator returns a real ExecutionPlan, not a quarantine dict.
    assert isinstance(result, ExecutionPlan), (
        f"Expected ExecutionPlan, got {type(result).__name__}: {result!r}"
    )

    # The seam captured exactly one round trip. Inspect the payload.
    assert len(captured_messages) == 1
    sent = captured_messages[0]

    # The orchestrator preserves the existing test seam: the messages
    # arriving at ``call_groq_json`` are the exact list that the boundary
    # will normalize. Today the orchestrator passes them through unchanged
    # to the seam (so the test fixture sees them pre-normalization). The
    # boundary normalization happens INSIDE ``call_groq_json`` itself —
    # this test verifies the seam still works AND that the normalizer
    # would translate the captured payload correctly. We re-run the
    # normalizer on the captured payload to lock the contract.
    from finflow_agent.llm import normalize_outbound_messages

    normalized = normalize_outbound_messages(sent)
    sent_roles_after_normalization = [m["role"] for m in normalized]
    for role in sent_roles_after_normalization:
        assert role in {"system", "user", "assistant", "tool"}, (
            f"Wire-format roles must be in the closed Groq set; got {role!r}. "
            f"Pre-normalization payload was {sent!r}"
        )

    # And the original LangChain payload contained the framework token
    # — proving this is the same shape that previously caused the 400
    # before the boundary fix landed.
    sent_roles_before_normalization = [m["role"] for m in sent]
    assert "human" in sent_roles_before_normalization, (
        "This test exists to lock the regression for `human`-role payloads "
        "produced by ChatPromptTemplate.format_messages(). If LangChain ever "
        "stops emitting `human`, update the assertion to whatever it now "
        "emits — but do NOT delete this test; the boundary normalization is "
        "the safety net regardless of upstream behavior."
    )
