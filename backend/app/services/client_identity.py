from __future__ import annotations


def resolve_client_identity(*, client_host: str, forwarded_for: str, trusted_proxy_ips: set[str]) -> str:
    client_host = client_host.strip()
    forwarded_for = forwarded_for.strip()

    if client_host and client_host in trusted_proxy_ips and forwarded_for:
        forwarded_ip = forwarded_for.split(",", 1)[0].strip()
        if forwarded_ip:
            return forwarded_ip

    if client_host:
        return client_host
    return "unknown"
