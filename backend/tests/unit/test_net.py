"""SSRF protection: what may be probed or cloned. DNS is faked, so these run offline."""

import socket

import pytest

from bento_core import net
from bento_core.config import settings


@pytest.fixture
def dns(monkeypatch):
    """Map hostnames to IPs without touching the network."""
    table: dict[str, list[str]] = {}

    def fake_getaddrinfo(host, *args, **kwargs):
        if host in table:
            return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in table[host]]
        try:  # literal IPs resolve to themselves
            import ipaddress
            ipaddress.ip_address(host)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, 0))]
        except ValueError:
            raise socket.gaierror("unknown host") from None

    monkeypatch.setattr(net.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(settings, "allow_private_targets", False)
    return table


def test_public_https_is_allowed(dns):
    dns["example.com"] = ["93.184.215.14"]
    assert net.probe_target_error("https://example.com/health") is None


@pytest.mark.parametrize("url", ["ftp://example.com", "file:///etc/passwd", "gopher://x", "javascript:alert(1)", "https://", "example.com"])
def test_only_http_urls(dns, url):
    assert net.probe_target_error(url) == "only http(s) URLs can be monitored"


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254", "0.0.0.0", "::1", "fc00::1", "fe80::1",
     "::ffff:127.0.0.1", "100.64.0.1"],
)
def test_private_and_internal_addresses_are_blocked(dns, ip):
    dns["internal.test"] = [ip]
    assert net.probe_target_error("http://internal.test/") is not None, ip


def test_literal_metadata_ip_is_blocked(dns):
    assert net.probe_target_error("http://169.254.169.254/latest/meta-data/") is not None


def test_any_private_record_blocks_the_host(dns):
    dns["mixed.test"] = ["93.184.215.14", "10.0.0.1"]
    assert net.probe_target_error("https://mixed.test") is not None


def test_private_targets_allowed_when_configured(dns, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_targets", True)
    dns["internal.test"] = ["10.0.0.5"]
    assert net.probe_target_error("http://internal.test/") is None


def test_unresolvable_host_is_left_to_the_probe(dns):
    assert net.probe_target_error("https://does-not-exist.test") is None


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://github.com/owner/repo", True),
        ("https://gitlab.com/group/project", True),
        ("https://GitHub.com/Owner/Repo.git", True),
        ("http://github.com/owner/repo", False),  # https only
        ("https://github.com/owner", False),
        ("https://evil.com/owner/repo", False),
        ("https://github.com.evil.com/owner/repo", False),
        ("ssh://git@github.com/owner/repo", False),
        ("https://user@github.com@evil.com/owner/repo", False),
    ],
)
def test_repo_urls(url, ok):
    assert (net.repo_url_error(url) is None) is ok


def test_repo_full_name_normalises():
    assert net.repo_full_name("https://github.com/Owner/Repo.git") == "owner/repo"
    assert net.repo_full_name("https://github.com/owner/repo/tree/main") == "owner/repo"
