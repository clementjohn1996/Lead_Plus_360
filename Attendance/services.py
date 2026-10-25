from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from HR import services as hr_services

from . import face, geo
from .models import AttendanceAttempt, AttendanceRecord, FaceTemplate

MAX_FAILED_ATTEMPTS = 8
LOCKOUT_MINUTES = 10


class PunchError(Exception):
    """A rejected enrollment/punch; the message is safe to show to the user."""


def _log(employee, kind, success, reason="", score=None, coords=None):
    lat, lng, acc = coords or (None, None, None)
    AttendanceAttempt.objects.create(
        employee=employee, kind=kind, success=success, reason=reason[:255], face_score=score,
        latitude=round(lat, 6) if lat is not None else None,
        longitude=round(lng, 6) if lng is not None else None,
        accuracy_m=acc,
    )


def _check_lockout(employee):
    since = timezone.now() - timedelta(minutes=LOCKOUT_MINUTES)
    failures = AttendanceAttempt.objects.filter(employee=employee, success=False, created_at__gte=since).count()
    if failures >= MAX_FAILED_ATTEMPTS:
        raise PunchError(f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes or contact HR.")


def _fail(employee, kind, message, score=None, coords=None):
    _log(employee, kind, False, message, score, coords)
    raise PunchError(message)


def enroll_face(employee, image_data):
    """Self-enrollment, allowed only while the employee has no enrolled face."""
    _check_lockout(employee)
    existing = FaceTemplate.objects.filter(employee=employee).count()
    if existing >= settings.FACE_MAX_TEMPLATES:
        raise PunchError("Enrollment is complete. Ask HR to reset it if you need to re-enroll.")
    try:
        img = face.decode_image(image_data)
        embedding, _ = face.extract_embedding(img)
    except face.FaceError as exc:
        _fail(employee, "enroll", str(exc))
    if existing:
        # Additional samples must match the first one so nobody can add a second identity.
        score = face.best_match(embedding, [t.embedding for t in employee.face_templates.all()])
        if not face.is_match(score):
            _fail(employee, "enroll", "This photo does not match your enrolled face.", score)
    template = FaceTemplate(employee=employee, embedding=embedding)
    template.snapshot.save(f"{employee.employee_code}.jpg", ContentFile(face.encode_jpeg(img)), save=False)
    template.save()
    _log(employee, "enroll", True)
    hr_services.sync_auto_tasks(employee)
    return existing + 1


def reset_face(employee):
    for template in employee.face_templates.all():
        if template.snapshot:
            template.snapshot.delete(save=False)
    employee.face_templates.all().delete()


def _verify(employee, kind, image_data, lat, lng, accuracy):
    """Common checks for check-in and check-out. Returns a dict of verified facts."""
    _check_lockout(employee)
    if employee.status == "exited":
        raise PunchError("This account is no longer active.")
    templates = [t.embedding for t in employee.face_templates.all()]
    if not templates:
        raise PunchError("Enroll your face first.")
    try:
        lat, lng, accuracy = geo.parse_coords(lat, lng, accuracy)
    except ValueError as exc:
        _fail(employee, kind, str(exc))
    coords = (lat, lng, accuracy)

    try:
        img = face.decode_image(image_data)
        embedding, _ = face.extract_embedding(img)
    except face.FaceError as exc:
        _fail(employee, kind, str(exc), coords=coords)
    score = face.best_match(embedding, templates)
    if not face.is_match(score):
        _fail(employee, kind, "Face not recognized.", score, coords)

    office, distance, inside = geo.nearest_office(lat, lng)
    if not inside:
        if not employee.can_punch_remotely:
            if office is None:
                _fail(employee, kind, "No office location is configured. Contact HR.", score, coords)
            _fail(employee, kind,
                  f"You are {int(distance)} m from {office.name}; move within {office.radius_m} m to punch.",
                  score, coords)
    elif not geo.accuracy_ok(accuracy):
        _fail(employee, kind,
              f"Location accuracy is too low ({int(accuracy) if accuracy else 'unknown'} m). Move near a window and retry.",
              score, coords)
    return {
        "img": img, "score": score, "lat": lat, "lng": lng, "accuracy": accuracy,
        "office": office if inside else None, "distance": distance, "inside": inside, "coords": coords,
    }


def _shift_deadline(employee, day):
    naive = datetime.combine(day, employee.shift_start) + timedelta(minutes=employee.grace_minutes)
    return timezone.make_aware(naive)


def check_in(employee, image_data, lat, lng, accuracy):
    now = timezone.now()
    today = timezone.localdate(now)
    if AttendanceRecord.objects.filter(employee=employee, date=today, check_in__isnull=False).exists():
        raise PunchError("You have already checked in today.")
    v = _verify(employee, "in", image_data, lat, lng, accuracy)
    if now > _shift_deadline(employee, today):
        status = "late"
    elif not v["inside"]:
        status = "remote"
    else:
        status = "present"
    try:
        with transaction.atomic():
            record = AttendanceRecord.objects.create(
                employee=employee, date=today, check_in=now, status=status,
                in_latitude=round(v["lat"], 6), in_longitude=round(v["lng"], 6),
                in_accuracy_m=v["accuracy"], in_distance_m=v["distance"], in_within_geofence=v["inside"],
                in_face_score=round(v["score"], 4), office=v["office"],
            )
    except IntegrityError:
        raise PunchError("You have already checked in today.")
    record.in_snapshot.save(f"{employee.employee_code}-{today}.jpg", ContentFile(face.encode_jpeg(v["img"])), save=True)
    _log(employee, "in", True, score=v["score"], coords=v["coords"])
    return record


def check_out(employee, image_data, lat, lng, accuracy):
    now = timezone.now()
    today = timezone.localdate(now)
    record = AttendanceRecord.objects.filter(employee=employee, date=today, check_in__isnull=False).first()
    if not record:
        raise PunchError("Check in first.")
    if record.check_out:
        raise PunchError("You have already checked out today.")
    if now - record.check_in < timedelta(minutes=settings.ATTENDANCE_MIN_CHECKOUT_GAP_MINUTES):
        raise PunchError("Please wait a moment before checking out.")
    v = _verify(employee, "out", image_data, lat, lng, accuracy)
    record.check_out = now
    record.out_latitude = round(v["lat"], 6)
    record.out_longitude = round(v["lng"], 6)
    record.out_accuracy_m = v["accuracy"]
    record.out_distance_m = v["distance"]
    record.out_within_geofence = v["inside"]
    record.out_face_score = round(v["score"], 4)
    if record.worked_hours < settings.ATTENDANCE_HALF_DAY_HOURS:
        record.status = "half_day"
    record.save()
    record.out_snapshot.save(f"{employee.employee_code}-{today}-out.jpg", ContentFile(face.encode_jpeg(v["img"])), save=True)
    _log(employee, "out", True, score=v["score"], coords=v["coords"])
    return record
