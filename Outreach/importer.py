"""Read leads from an Excel (.xlsx) or CSV file into prospects, skipping duplicates."""
import csv
import io
import re

from .profiler import domain_of, normalize_url

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SYNONYMS = {
    "company": ["company", "company name", "organisation", "organization", "business", "business name", "firm", "account", "name of company"],
    "contact_name": ["contact", "contact name", "name", "full name", "person", "owner", "lead name", "decision maker"],
    "contact_title": ["title", "designation", "job title", "role", "position"],
    "email": ["email", "e-mail", "email address", "mail", "email id", "contact email"],
    "phone": ["phone", "mobile", "telephone", "contact number", "phone number", "whatsapp", "mobile number", "tel"],
    "website": ["website", "web", "url", "site", "domain", "web site", "company website"],
    "city": ["city", "town", "location"],
    "country": ["country"],
    "industry": ["industry", "sector", "category", "niche", "business type"],
}


def _norm(h):
    return re.sub(r"[^a-z0-9 ]", "", str(h or "").lower().replace("_", " ")).strip()


def map_headers(headers):
    mapping = {}
    for idx, h in enumerate(headers):
        n = _norm(h)
        for field, names in SYNONYMS.items():
            if field not in mapping.values() and n in names:
                mapping[idx] = field
                break
    return mapping


def read_rows(uploaded):
    """Yield list-of-lists rows from an uploaded .xlsx/.csv file."""
    name = (uploaded.name or "").lower()
    if uploaded.size > MAX_BYTES:
        raise ValueError("File is larger than 5 MB.")
    data = uploaded.read()
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        return [["" if c is None else str(c).strip() for c in row] for row in ws.iter_rows(values_only=True)]
    if name.endswith(".csv"):
        text = data.decode("utf-8-sig", errors="replace")
        return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text))]
    raise ValueError("Please upload an .xlsx or .csv file.")


def import_prospects(rows, user, source="import"):
    """Create prospects from rows (first row = headers). Returns a summary dict."""
    from LeadManager.models import Lead

    from .models import Prospect, ProspectEvent

    summary = {"created": 0, "duplicates": 0, "invalid": 0, "mapped": [], "unmapped": [], "errors": []}
    if not rows:
        summary["errors"].append("The file is empty.")
        return summary
    headers = rows[0]
    mapping = map_headers(headers)
    summary["mapped"] = [f"{headers[i]} → {f}" for i, f in mapping.items()]
    summary["unmapped"] = [h for i, h in enumerate(headers) if i not in mapping and str(h).strip()]
    if "company" not in mapping.values() and "contact_name" not in mapping.values():
        summary["errors"].append("Could not find a company or name column. Rename a header to 'Company'.")
        return summary
    seen_email = set(Prospect.objects.exclude(email="").values_list("email", flat=True))
    seen_email |= set(Lead.objects.exclude(email="").values_list("email", flat=True))
    seen_email = {e.lower() for e in seen_email}
    seen_domain = set(Prospect.objects.exclude(domain="").values_list("domain", flat=True))
    for row in rows[1:MAX_ROWS + 1]:
        rec = {field: (row[i].strip() if i < len(row) else "") for i, field in mapping.items()}
        if not any(rec.values()):
            continue
        company = rec.get("company") or rec.get("contact_name", "")
        email = rec.get("email", "").lower()
        if email and not EMAIL_RE.match(email):
            email = ""
            summary["invalid"] += 1
        website = normalize_url(rec.get("website", "")) if rec.get("website") else ""
        domain = domain_of(website) if website else ""
        if not company or (not email and not website and not rec.get("phone")):
            summary["invalid"] += 1
            continue
        if (email and email in seen_email) or (domain and domain in seen_domain):
            summary["duplicates"] += 1
            continue
        prospect = Prospect.objects.create(
            company=company[:200], contact_name=rec.get("contact_name", "")[:160] if rec.get("company") else "",
            contact_title=rec.get("contact_title", "")[:120], email=email, phone=rec.get("phone", "")[:40],
            website=website[:300], domain=domain[:200], city=rec.get("city", "")[:100],
            country=rec.get("country", "")[:80], industry=rec.get("industry", "")[:100],
            source=source, owner=user, email_status="unknown" if email else "unknown",
        )
        ProspectEvent.objects.create(prospect=prospect, kind="import", body="Imported from spreadsheet.", created_by=user)
        if email:
            seen_email.add(email)
        if domain:
            seen_domain.add(domain)
        summary["created"] += 1
    return summary
