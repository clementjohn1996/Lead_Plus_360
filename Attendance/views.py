import csv
import json
from calendar import monthrange
from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from Control.permissions import hr_required, is_hr
from HR.models import Employee

from . import services
from .models import AttendanceAttempt, AttendanceRecord, FaceTemplate, OfficeLocation


def _employee_or_403(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied
    return employee


def _payload(request):
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _record_json(record):
    local = timezone.localtime
    return {
        "status": record.get_status_display(),
        "check_in": local(record.check_in).strftime("%I:%M %p") if record.check_in else None,
        "check_out": local(record.check_out).strftime("%I:%M %p") if record.check_out else None,
    }


@login_required
@never_cache
def punch_page(request):
    employee = _employee_or_403(request)
    today = timezone.localdate()
    record = AttendanceRecord.objects.filter(employee=employee, date=today).first()
    return render(request, "Attendance/punch.html", {
        "emp": employee,
        "record": record,
        "enrolled": employee.face_templates.exists(),
        "history": AttendanceRecord.objects.filter(employee=employee)[:14],
        "offices": OfficeLocation.objects.filter(is_active=True),
    })


@login_required
@require_POST
def api_enroll(request):
    employee = _employee_or_403(request)
    data = _payload(request)
    try:
        count = services.enroll_face(employee, data.get("image"))
    except services.PunchError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "samples": count})


@login_required
@require_POST
def api_punch(request):
    employee = _employee_or_403(request)
    data = _payload(request)
    action = data.get("action")
    if action not in ("in", "out"):
        return JsonResponse({"ok": False, "error": "Unknown action."}, status=400)
    func = services.check_in if action == "in" else services.check_out
    try:
        record = func(employee, data.get("image"), data.get("lat"), data.get("lng"), data.get("accuracy"))
    except services.PunchError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "record": _record_json(record)})


@hr_required
@require_POST
def reset_face(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    services.reset_face(employee)
    messages.success(request, f"Face enrollment reset for {employee.full_name}. They can re-enroll now.")
    return redirect("hr_employee_detail", pk=employee.pk)


@login_required
def snapshot(request, record_id, which):
    record = get_object_or_404(AttendanceRecord.objects.select_related("employee"), pk=record_id)
    own = getattr(request.user, "employee", None)
    if not (is_hr(request.user) or (own and own.pk == record.employee_id)):
        raise PermissionDenied
    field = {"in": record.in_snapshot, "out": record.out_snapshot}.get(which)
    if not field:
        raise Http404
    response = FileResponse(field.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    return response


def _parse_date(value, default):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


@hr_required
def hr_dashboard(request):
    day = _parse_date(request.GET.get("date"), timezone.localdate())
    employees = Employee.objects.exclude(status="exited").select_related("user", "department")
    records = {r.employee_id: r for r in AttendanceRecord.objects.filter(date=day)}
    rows = [{"emp": e, "rec": records.get(e.pk)} for e in employees]
    summary = {
        "total": len(rows),
        "present": sum(1 for r in rows if r["rec"] and r["rec"].status in ("present", "remote")),
        "late": sum(1 for r in rows if r["rec"] and r["rec"].status == "late"),
        "half_day": sum(1 for r in rows if r["rec"] and r["rec"].status == "half_day"),
        "absent": sum(1 for r in rows if not r["rec"]),
    }
    from datetime import timedelta

    failures = AttendanceAttempt.objects.filter(
        success=False, created_at__gte=timezone.now() - timedelta(days=1)
    ).select_related("employee__user")[:15]
    return render(request, "Attendance/hr_dashboard.html", {
        "day": day, "rows": rows, "summary": summary, "failures": failures,
        "is_today": day == timezone.localdate(),
    })


def _monthly_rows(year, month):
    days = monthrange(year, month)[1]
    first, last = date(year, month, 1), date(year, month, days)
    from django.conf import settings

    off_days = set(settings.WEEKLY_OFF_DAYS)
    workdays = sum(1 for d in range(1, days + 1) if date(year, month, d).weekday() not in off_days)
    today = timezone.localdate()
    counted = sum(
        1 for d in range(1, days + 1)
        if date(year, month, d).weekday() not in off_days and date(year, month, d) <= today
    )
    records = AttendanceRecord.objects.filter(date__range=(first, last))
    by_emp = {}
    for r in records:
        by_emp.setdefault(r.employee_id, []).append(r)
    rows = []
    for e in Employee.objects.exclude(status="exited").select_related("user", "department"):
        recs = by_emp.get(e.pk, [])
        present = sum(1 for r in recs if r.status in ("present", "remote", "late"))
        half = sum(1 for r in recs if r.status == "half_day")
        late = sum(1 for r in recs if r.status == "late")
        hours = sum(r.worked_hours or 0 for r in recs)
        attended = present + half * 0.5
        rows.append({
            "emp": e, "present": present, "half": half, "late": late,
            "absent": max(counted - present - half, 0), "hours": round(hours, 1),
            "percent": round(100 * attended / counted) if counted else 0,
        })
    return rows, workdays


@hr_required
def monthly_report(request):
    today = timezone.localdate()
    try:
        year, month = int(request.GET.get("year", today.year)), int(request.GET.get("month", today.month))
        date(year, month, 1)
    except ValueError:
        year, month = today.year, today.month
    rows, workdays = _monthly_rows(year, month)
    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="attendance-{year}-{month:02d}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Code", "Name", "Department", "Present", "Half days", "Late", "Absent", "Hours", "Attendance %"])
        for r in rows:
            writer.writerow([
                r["emp"].employee_code, r["emp"].full_name, r["emp"].department or "",
                r["present"], r["half"], r["late"], r["absent"], r["hours"], r["percent"],
            ])
        return response
    return render(request, "Attendance/monthly.html", {
        "rows": rows, "year": year, "month": month, "workdays": workdays,
        "month_label": date(year, month, 1).strftime("%B %Y"),
        "years": range(today.year - 2, today.year + 1), "months": range(1, 13),
    })


class OfficeForm(forms.ModelForm):
    class Meta:
        model = OfficeLocation
        fields = ["name", "latitude", "longitude", "radius_m", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")
        self.fields["latitude"].widget.attrs["step"] = "any"
        self.fields["longitude"].widget.attrs["step"] = "any"


@hr_required
def offices(request, pk=None):
    instance = get_object_or_404(OfficeLocation, pk=pk) if pk else None
    if request.method == "POST":
        form = OfficeForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Office location saved.")
            return redirect("attendance_offices")
    else:
        form = OfficeForm(instance=instance)
    return render(request, "Attendance/offices.html", {
        "form": form, "offices": OfficeLocation.objects.all(), "editing": instance,
    })


@hr_required
@require_POST
def office_delete(request, pk):
    get_object_or_404(OfficeLocation, pk=pk).delete()
    messages.success(request, "Office location deleted.")
    return redirect("attendance_offices")
