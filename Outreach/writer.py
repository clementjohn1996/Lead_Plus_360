"""Rule-based email writer: short, plain, signal-led, no pitch in the first email."""
import re

from . import signals as sig

BANNED = [
    "i hope this email finds you", "touch base", "circle back", "synergy", "game-changer", "game changer",
    "revolutionary", "cutting-edge", "cutting edge", "best-in-class", "world-class", "leverage",
    "just checking in", "quick question", "limited time", "act now", "guarantee", "100%", "free!!!",
]
WORD_LIMITS = {1: 75, 2: 75, 3: 40}


def words(text):
    return len(re.findall(r"\b[\w'’-]+\b", text))


def violations(text):
    low = text.lower()
    return [b for b in BANNED if b in low]


def _opener(prospect):
    for key in sorted(prospect.signals, key=lambda k: -sig.SIGNALS.get(k, ("", "", 0))[2]):
        template = sig.SIGNALS.get(key, ("", "", 0, ""))[3]
        if template:
            return template.format(company=prospect.company)
    return f"I came across {prospect.company}"


def _greeting(prospect):
    return f"Hi {prospect.first_name}," if prospect.first_name else f"Hi team at {prospect.company},"


def _trim(text, limit):
    parts = text.split()
    return text if len(parts) <= limit else " ".join(parts[:limit]).rstrip(",;:") + "."


def _signoff(settings):
    lines = ["Thanks,", settings.sender_name or "The team"]
    lines += [ln for ln in settings.signature.splitlines() if ln.strip()][:3]
    return "\n".join(lines)


def build_sequence(prospect, campaign, settings):
    """Return [(step, subject, body), ...] for a three-email sequence."""
    opener = _opener(prospect)
    offer = _trim(campaign.offer.strip().rstrip("."), 28)
    cta = campaign.call_to_action.strip() or "Worth a quick chat this week?"
    greeting = _greeting(prospect)
    sign = _signoff(settings)

    if campaign.framework == "aida":
        middle = f"We {offer[0].lower() + offer[1:]}." if offer else ""
    elif campaign.framework == "bab":
        middle = f"Companies we work with go from that to a steady flow of enquiries. We {offer[0].lower() + offer[1:]}." if offer else ""
    else:
        middle = f"It tends to cost businesses enquiries they never see. We {offer[0].lower() + offer[1:]}." if offer else ""

    first = f"{greeting}\n\n{opener[0].upper() + opener[1:]}. {middle}\n\n{cta}\n\n{sign}"
    second = (f"{greeting}\n\nFollowing up on my note about {prospect.company}. "
              f"If the timing is wrong, no problem - I can send a short checklist instead of a call.\n\n{sign}")
    third = f"{greeting}\n\nI'll stop here so I don't clutter your inbox. If this becomes a priority, just reply and I'll pick it up.\n\n{sign}"

    subject1 = f"{prospect.company}: one thing I noticed"
    return [
        (1, subject1, first),
        (2, f"Re: {subject1}", second),
        (3, f"Re: {subject1}", third),
    ]
