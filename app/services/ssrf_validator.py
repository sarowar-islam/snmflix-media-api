import ipaddress
import socket
from urllib.parse import urlsplit


class SSRFSecurityError(Exception):
    """Raised when an address or target violates SSRF security rules."""
    pass


class InvalidURLError(Exception):
    """Raised when a URL is structurally invalid or unresolvable."""
    pass


# Forbidden IP networks that should never be accessed by the backend
FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network (only valid as source address)
    ipaddress.ip_network("10.0.0.0/8"),         # Private RFC1918
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space (Carrier-Grade NAT)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local / Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # Private RFC1918
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),     # Private RFC1918
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6 Networks
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("100::/64"),           # Discard prefix
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local Unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
]

# Prohibited hostnames and suffixes
FORBIDDEN_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}

FORBIDDEN_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home",
    ".corp",
    ".localdomain",
)


def is_ip_forbidden(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any restricted or private network."""
    # Check standard properties
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True

    # Handle IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return is_ip_forbidden(ip.ipv4_mapped)

    # Check explicit network definitions
    for network in FORBIDDEN_NETWORKS:
        if ip in network:
            return True

    return False


def validate_url_security(url: str) -> None:
    """
    Validate a URL to defend against Server-Side Request Forgery (SSRF)
    and dangerous schemes before passing it to yt-dlp.
    """
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL must be a non-empty string")

    url = url.strip()
    if len(url) > 2048:
        raise InvalidURLError("URL length exceeds maximum allowed limit of 2048 characters")

    try:
        parsed = urlsplit(url)
    except Exception as e:
        raise InvalidURLError(f"Malformed URL structure: {e}") from e

    # 1. Scheme validation: only http and https allowed
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise SSRFSecurityError(
            f"Unsupported URL scheme '{scheme}'. Only HTTP and HTTPS are permitted."
        )

    # 2. Hostname validation
    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError("URL must contain a valid hostname")

    # Reject credentials in URL (e.g. http://user:pass@evil.com)
    if parsed.username or parsed.password:
        raise SSRFSecurityError("URLs containing embedded credentials are not allowed")

    # Port validation
    if parsed.port is not None:
        if parsed.port < 1 or parsed.port > 65535:
            raise InvalidURLError(f"Invalid port number: {parsed.port}")

    hostname_lower = hostname.lower()

    # 3. Check against forbidden hostnames and domain suffixes
    if hostname_lower in FORBIDDEN_HOSTNAMES:
        raise SSRFSecurityError(f"Access to restricted hostname '{hostname}' is prohibited.")

    if any(hostname_lower.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
        raise SSRFSecurityError(
            f"Access to private/internal domain '{hostname}' is prohibited."
        )

    # 4. Check if hostname is directly an IP address literal
    try:
        ip = ipaddress.ip_address(hostname_lower.strip("[]"))
    except ValueError:
        ip = None

    if ip is not None:
        if is_ip_forbidden(ip):
            raise SSRFSecurityError(
                f"Access to private, loopback, or restricted IP address '{ip}' is prohibited."
            )
        # Directly validated IP literal
        return

    # 5. DNS Resolution pre-check
    target_port = parsed.port or (443 if scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(
            hostname,
            target_port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as e:
        raise InvalidURLError(f"Unable to resolve host '{hostname}': {e}") from e
    except Exception as e:
        raise InvalidURLError(f"DNS resolution failed for '{hostname}': {e}") from e

    if not addr_info:
        raise InvalidURLError(f"No IP address records found for '{hostname}'")

    for entry in addr_info:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFSecurityError(f"Invalid resolved IP address: '{ip_str}'")

        if is_ip_forbidden(ip):
            raise SSRFSecurityError(
                f"Resolved host '{hostname}' points to restricted IP address '{ip}'."
            )
