"""URL safety checks (SSRF protection for probes and repo scans)."""

import ipaddress
import socket
from urllib.parse import urlparse

from .config import settings

REPO_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}


def _is_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # unresolvable: the probe itself will report the failure
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])  # drop an IPv6 zone id
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped  # ::ffff:127.0.0.1 is 127.0.0.1
        # Anything not globally routable: private, loopback, link-local (cloud metadata), reserved,
        # multicast, and shared/carrier-grade NAT space (100.64.0.0/10), which is_private misses.
        if not ip.is_global or ip.is_multicast:
            return True
    return False


def probe_target_error(url: str) -> str | None:
    """Return a reason the URL must not be probed, or None if it is allowed."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "only http(s) URLs can be monitored"
    if not settings.allow_private_targets and _is_private(parsed.hostname):
        return "private and internal addresses cannot be monitored"
    return None


def repo_url_error(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in REPO_HOSTS:
        return f"repository must be an https URL on {', '.join(sorted(REPO_HOSTS))}"
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return "repository URL must look like https://github.com/owner/name"
    return None


def repo_full_name(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return f"{parts[0]}/{parts[1].removesuffix('.git')}".lower()
