"""Fetch a prospect's public homepage and turn it into signals.

`analyze()` is a pure function (easy to test). `fetch()` is SSRF-safe: it refuses private,
loopback and link-local addresses and re-checks every redirect.
"""
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone

from . import signals as sig

MAX_BYTES = 600_000
TIMEOUT = 8
UA = "Mozilla/5.0 (compatible; GrowthForgeBot/1.0; +public-homepage-check)"


def normalize_url(raw):
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    return raw


def domain_of(raw):
    host = urllib.parse.urlparse(normalize_url(raw)).hostname or ""
    return host.lower().removeprefix("www.")


def _is_public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return bool(infos)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url, max_redirects=3):
    """Return (final_url, html) or raise ValueError with a short reason."""
    opener = urllib.request.build_opener(_NoRedirect)
    current = normalize_url(url)
    for _ in range(max_redirects + 1):
        parts = urllib.parse.urlparse(current)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("Unsupported address")
        if not _is_public_host(parts.hostname):
            raise ValueError("Address is not a public website")
        request = urllib.request.Request(current, headers={"User-Agent": UA, "Accept": "text/html"})
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                raw = response.read(MAX_BYTES)
                charset = response.headers.get_content_charset() or "utf-8"
                return current, raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                current = urllib.parse.urljoin(current, exc.headers["Location"])
                continue
            raise ValueError(f"Site returned HTTP {exc.code}")
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise ValueError(f"Could not reach site ({getattr(exc, 'reason', exc)})")
    raise ValueError("Too many redirects")


def fetch_robots(url):
    parts = urllib.parse.urlparse(url)
    try:
        _, text = fetch(f"{parts.scheme}://{parts.netloc}/robots.txt", max_redirects=1)
        return text
    except ValueError:
        return ""


def analyze(html, final_url="", robots=""):
    """Return (set_of_signal_keys, data_dict) from homepage HTML."""
    low = html.lower()
    found = set()
    data = {"tech": []}
    if final_url.startswith("http://"):
        found.add("NO_HTTPS")
    if 'name="viewport"' not in low and "name='viewport'" not in low:
        found.add("NOT_MOBILE_FRIENDLY")
    has_form = "<form" in low or any(w in low for w in ("calendly.com", "book now", "book online", "tawk.to", "livechat", "whatsapp"))
    if not has_form:
        found.add("NO_ONLINE_BOOKING")
    if "application/ld+json" not in low and "itemscope" not in low:
        found.add("NO_SCHEMA_MARKUP")
    if not any(w in low for w in ("/blog", "/news", "/articles", ">blog<", ">news<")):
        found.add("BLOG_STALE")
    if "googleadservices.com" in low or "googlesyndication" in low or re.search(r"['\"]aw-\d{6,}", low):
        found.add("RUNNING_GOOGLE_ADS")
    if "connect.facebook.net" in low or "fbq(" in low:
        found.add("RUNNING_META_ADS")
    credit = re.search(r"(website|web design|designed|developed|built|powered)\s+by\s+(?!us\b)([^<]{2,40})", low)
    if credit and "wordpress" not in credit.group(2) and "wix" not in credit.group(2) and "shopify" not in credit.group(2):
        found.add("INCUMBENT_AGENCY")
        data["agency_credit"] = credit.group(2).strip()[:40]
    if re.search(r"user-agent:\s*(gptbot|claudebot|ccbot|perplexitybot|google-extended)[^\n]*\n\s*disallow:\s*/", robots.lower()):
        found.add("BLOCKS_AI_CRAWLERS")
    if any(w in low for w in ("/careers", "/jobs", "we're hiring", "we are hiring", "join our team")):
        found.add("HIRING_ROLE")
    for name, needles in sig.TECH.items():
        if any(n in low for n in needles):
            data["tech"].append(name)
    return found, data


def score_prospect(prospect):
    """Fit score 0-10 plus a plain-English reason."""
    score, reasons = 0, []
    if prospect.email and prospect.email_status != "invalid":
        score += 2
        reasons.append("has a usable email")
    if prospect.contact_name:
        score += 1
        reasons.append("named contact")
    for key in prospect.signals:
        weight = sig.SIGNALS.get(key, ("", "", 0))[2]
        if weight:
            score += weight
            reasons.append(sig.label(key).lower())
    score = max(0, min(10, score))
    return score, ("Because: " + ", ".join(reasons) + ".") if reasons else "No strong signals yet."


def scan_prospect(prospect, confirmed, user=None):
    """Scan one prospect. Returns a short human message."""
    from .models import ProspectEvent

    confirmed = set(confirmed)
    found, data, message = set(), {}, ""
    if not prospect.website.strip():
        found.add("NO_WEBSITE")
        message = "No website on file."
    else:
        try:
            final_url, html = fetch(prospect.website)
            robots = fetch_robots(final_url) if "BLOCKS_AI_CRAWLERS" in confirmed else ""
            found, data = analyze(html, final_url, robots)
            message = "Homepage scanned."
        except ValueError as exc:
            message = f"Scan failed: {exc}"
            ProspectEvent.objects.create(prospect=prospect, kind="scan", body=message, created_by=user)
            return message
    found &= confirmed
    prospect.set_signals(found)
    prospect.signal_data = data
    prospect.last_scanned = timezone.now()
    prospect.score, prospect.score_reason = score_prospect(prospect)
    if prospect.status == "new":
        prospect.status = "profiled"
    prospect.save()
    ProspectEvent.objects.create(
        prospect=prospect, kind="scan", created_by=user,
        body=f"{message} {len(found)} confirmed signal(s) found; fit score {prospect.score}/10.",
    )
    return message
