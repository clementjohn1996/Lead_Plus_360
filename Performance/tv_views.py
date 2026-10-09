"""Public token-protected TV display endpoints."""
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.views.decorators.clickjacking import xframe_options_sameorigin

from . import bde
from . import services
from .models import TVDisplay, TVPoster
from HR.models import Employee


def _display(token):
    try:
        return TVDisplay.objects.select_related("department").get(token=token, is_active=True)
    except TVDisplay.DoesNotExist:
        raise Http404


def _photo_url(request, employee):
    profile = getattr(employee.user, "profile", None)
    photo = getattr(profile, "profile_picture", None) if profile else None
    if photo:
        try:
            return request.build_absolute_uri(photo.url)
        except ValueError:
            pass
    return ""


def _performance_slides(request, display, month):
    bde_ids = set(bde.bde_employees().values_list("pk", flat=True))
    rows = [r for r in services.leaderboard(month, display.department, tv_only=True) if r["employee"].pk in bde_ids]
    slides = []
    bde_rows = {r["employee"].pk: r for r in bde.dashboard(Employee.objects.filter(pk__in=[x["employee"].pk for x in rows]), today=month)["rows"]}
    for r in rows:
        emp = r["employee"]
        br = bde_rows.get(emp.pk)
        rec = br.get("record") if br else None
        if rec:
            cfg = bde.BDEConfig.get()
            segments = bde.segments(rec, cfg)
            pct = float(rec.achievement_pct)
            colour = rec.effective_colour
            status = rec.get_status_display()
            target = float(rec.target)
            revenue = float(rec.revenue)
            slab = rec.slab
        else:
            segments = []
            pct = float(r["score"] or 0)
            colour = "green" if pct >= 81 else "yellow" if pct >= 51 else "red"
            status = r["label"]
            target = revenue = None
            slab = None
        slides.append({
            "type": "performance",
            "name": emp.full_name,
            "designation": emp.designation,
            "department": emp.department.name if emp.department else "",
            "photo": _photo_url(request, emp),
            "initials": "".join(p[0] for p in emp.full_name.split()[:2]).upper(),
            "rank": r["rank"],
            "score": pct,
            "rating": status,
            "colour": colour,
            "target": target,
            "revenue": revenue,
            "slab": slab,
            "segments": segments,
            "kpis": [
                {"name": k["kpi"].name, "percent": k["percent"], "unit": k["kpi"].unit,
                 "actual": k["actual"], "target": k["target"]}
                for k in r["kpis"] if k["percent"] is not None
            ],
        })
    return slides


def _celebration_slides(request, display, today):
    qs = Employee.objects.select_related("user", "department").filter(status="active", show_on_tv=True)
    if display.department_id:
        qs = qs.filter(department_id=display.department_id)
    slides = []
    for emp in qs:
        photo = _photo_url(request, emp)
        if emp.date_of_birth and (emp.date_of_birth.month, emp.date_of_birth.day) == (today.month, today.day):
            slides.append({
                "type": "birthday", "name": emp.full_name, "designation": emp.designation,
                "department": emp.department.name if emp.department else "", "photo": photo,
                "initials": "".join(p[0] for p in emp.full_name.split()[:2]).upper(),
                "message": "Wishing you a fantastic birthday!",
            })
        if emp.date_of_joining and (emp.date_of_joining.month, emp.date_of_joining.day) == (today.month, today.day):
            years = max(1, today.year - emp.date_of_joining.year)
            slides.append({
                "type": "anniversary", "name": emp.full_name, "designation": emp.designation,
                "department": emp.department.name if emp.department else "", "photo": photo,
                "initials": "".join(p[0] for p in emp.full_name.split()[:2]).upper(),
                "years": years,
                "message": f"Celebrating {years} year{'s' if years != 1 else ''} with the team!",
            })
    return slides


def _payload(request, display):
    bde.ensure_up_to_date()
    today = timezone.localdate()
    month = bde.last_completed_month(today)
    slides = _celebration_slides(request, display, today)
    slides += _performance_slides(request, display, month)
    slides += [
        {
            "type": "poster", "title": p.title, "subtitle": p.subtitle,
            "image": request.build_absolute_uri(p.image.url) if p.image else "",
            "seconds": p.seconds,
        }
        for p in TVPoster.objects.filter(is_active=True)
    ]
    return {
        "title": display.name,
        "month": month.strftime("%B %Y"),
        "seconds": display.seconds_per_slide,
        "generated": timezone.localtime().strftime("%d %b %Y, %I:%M %p"),
        "slides": slides,
    }


def _headers(response):
    response["Cache-Control"] = "no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    return response


@require_GET
@never_cache
@xframe_options_sameorigin
def tv_page(request, token):
    display = _display(token)
    return _headers(render(request, "Performance/tv.html", {"display": display, "token": token}))


@require_GET
@never_cache
def tv_data(request, token):
    return _headers(JsonResponse(_payload(request, _display(token))))
