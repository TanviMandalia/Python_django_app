"""
core/ip_utils.py

Secure Client IP Resolution, Verification, and Privacy Sanitation Utilities.

Production Hosting Context (Render Cloud):
- Render routes incoming public HTTP(S) traffic through reverse proxies and load balancers.
- The immediate peer address connecting to the Gunicorn WSGI container (request.META['REMOTE_ADDR'])
  is Render's internal reverse proxy, residing in private container network space (RFC 1918):
  10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, or loopback 127.0.0.1 / ::1.
- Render forwards the client IP in `X-Forwarded-For` and, in many edge ingress configurations,
  `CF-Connecting-IP`, `X-Render-Client-IP`, or `True-Client-IP`.

Spoofing Defense & Multi-Proxy Traversal:
- Forwarded headers are ONLY trusted when request.META['REMOTE_ADDR'] belongs to a trusted proxy.
- If REMOTE_ADDR is an untrusted address (e.g. direct client connection in local dev or untrusted origin),
  forwarded headers are completely ignored, because any client could have crafted arbitrary values.
- When traversing `X-Forwarded-For`, the chain is evaluated from RIGHT to LEFT:
  Each trustworthy proxy appends the incoming IP it observed. An attacker may prepend fake IPs:
  `fake_client, real_client, proxy1`.
  By scanning backwards from the trusted edge, the first non-trusted address encountered is the authentic
  client IP.
- All IP addresses are strictly validated and normalized using Python's standard `ipaddress` module.
- Malformed inputs, injection attempts, and fake addresses fail safely without raising unhandled exceptions.
- Does not invent an IP address if the true client address cannot be determined.
"""

import hashlib
import ipaddress
import logging
from urllib.parse import urlparse
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Standard private and loopback networks used by reverse proxies, containers, and internal routers
DEFAULT_TRUSTED_PROXY_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),   # IPv6 Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local
]


def parse_ip(ip_str):
    """
    Safely validate and parse an IPv4 or IPv6 address string.
    Strips ports (e.g. 192.0.2.1:8080) and brackets (e.g. [2001:db8::1]).
    Returns an ipaddress.IPv4Address or ipaddress.IPv6Address object, or None if invalid.
    """
    if not ip_str or not isinstance(ip_str, str):
        return None
    cleaned = ip_str.strip()
    if not cleaned:
        return None

    # Handle IPv6 brackets: [2001:db8::1] or [2001:db8::1]:8080
    if cleaned.startswith("[") and "]" in cleaned:
        cleaned = cleaned[1:cleaned.index("]")]
    elif ":" in cleaned and cleaned.count(":") == 1 and "." in cleaned:
        # IPv4 with port: 198.51.100.1:443
        cleaned = cleaned.split(":")[0]

    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        return None


def is_trusted_proxy(ip_obj):
    """
    Check if a parsed IP address belongs to trusted proxy networks.
    Supports settings.TRUSTED_PROXIES overrides or standard private subnets.
    """
    if not ip_obj:
        return False

    custom_proxies = getattr(settings, "TRUSTED_PROXIES", None)
    if custom_proxies:
        for proxy_entry in custom_proxies:
            try:
                entry_str = str(proxy_entry).strip()
                if "/" in entry_str:
                    if ip_obj in ipaddress.ip_network(entry_str, strict=False):
                        return True
                else:
                    if ip_obj == ipaddress.ip_address(entry_str):
                        return True
            except ValueError:
                continue

    for net in DEFAULT_TRUSTED_PROXY_NETWORKS:
        if ip_obj in net:
            return True

    return False


def get_client_ip(request):
    """
    Resolve the genuine client IP address for a Django request.
    Handles Render reverse proxy and protects against X-Forwarded-For spoofing.
    Returns normalized IP string, or '' if unresolvable.
    """
    remote_addr_raw = request.META.get("REMOTE_ADDR", "")
    remote_ip = parse_ip(remote_addr_raw)

    # In test environments without a mock proxy, allow header trust if explicitly set
    allow_header_trust = getattr(settings, "TRUST_ALL_PROXIES_IN_TEST", False)

    # 1. If REMOTE_ADDR is missing or NOT a trusted proxy, do NOT trust forwarded headers!
    if not remote_ip or (not is_trusted_proxy(remote_ip) and not allow_header_trust):
        if remote_ip:
            return str(remote_ip)
        return None

    # 2. REMOTE_ADDR is a trusted proxy. Check provider-specific edge headers first.
    # Cloudflare and Render edge proxies set CF-Connecting-IP, X-Render-Client-IP, or True-Client-IP
    for edge_header in ("HTTP_CF_CONNECTING_IP", "HTTP_X_RENDER_CLIENT_IP", "HTTP_TRUE_CLIENT_IP"):
        val = request.META.get(edge_header)
        if val:
            parsed = parse_ip(val)
            if parsed and not is_trusted_proxy(parsed):
                return str(parsed)

    # 3. Traverse X-Forwarded-For from right to left (nearest proxy backwards).
    # Each proxy appends its incoming peer; the rightmost non-proxy IP is the authentic client.
    xff_raw = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff_raw:
        parts = [p.strip() for p in xff_raw.split(",") if p.strip()]
        for part in reversed(parts):
            parsed = parse_ip(part)
            if not parsed:
                continue
            if not is_trusted_proxy(parsed):
                return str(parsed)

        # If every IP in the chain is in a private/trusted subnet (e.g. local dev / internal container test)
        for part in parts:
            parsed = parse_ip(part)
            if parsed:
                return str(parsed)

    # 4. Fallback to REMOTE_ADDR
    if remote_ip:
        return str(remote_ip)

    return None


def generate_pseudonymous_visitor_id(ip_str, user_agent="", date_salt=None):
    """
    Generate a privacy-safe pseudonymous visitor identifier.
    Uses SHA-256 hash of IP + user agent + daily or secret salt.
    Prevents long-term cross-session fingerprinting while allowing daily/session visitor deduplication.
    """
    secret = getattr(settings, "SECRET_KEY", "default-salt")
    if not date_salt:
        date_salt = timezone.now().strftime("%Y-%m-%d")
    raw = f"{ip_str}:{user_agent[:100]}:{secret[:16]}:{date_salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def sanitize_referrer_url(referrer_raw):
    """
    Sanitize referring URLs to strip query parameters and sensitive tokens.
    Retains scheme, domain, and path only (e.g. https://www.google.com/search).
    Prevents leakage of session tokens, passwords, search queries, or patient identifiers.
    """
    if not referrer_raw or not isinstance(referrer_raw, str):
        return ""
    try:
        parsed = urlparse(referrer_raw.strip())
        if not parsed.scheme or not parsed.netloc:
            return ""
        # Return scheme + netloc + path without query or fragment
        clean_path = parsed.path or "/"
        return f"{parsed.scheme}://{parsed.netloc}{clean_path}"[:500]
    except Exception:
        return ""
