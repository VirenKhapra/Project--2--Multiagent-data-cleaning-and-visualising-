from app.services.client_identity import resolve_client_identity


def test_request_identity_ignores_untrusted_forwarded_for():
    assert resolve_client_identity(
        client_host="203.0.113.10",
        forwarded_for="198.51.100.25",
        trusted_proxy_ips=set(),
    ) == "203.0.113.10"


def test_request_identity_uses_forwarded_for_from_trusted_proxy():
    assert resolve_client_identity(
        client_host="203.0.113.10",
        forwarded_for="198.51.100.25, 198.51.100.26",
        trusted_proxy_ips={"203.0.113.10"},
    ) == "198.51.100.25"
