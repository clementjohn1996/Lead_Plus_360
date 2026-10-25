from django.db import models
from django.utils import timezone

from .storage import private_storage


class OfficeLocation(models.Model):
    name = models.CharField(max_length=120)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_m = models.PositiveIntegerField(default=150, help_text="Allowed distance from the point, in metres.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FaceTemplate(models.Model):
    """One enrolled face embedding (128-d SFace vector stored as JSON)."""

    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="face_templates")
    embedding = models.JSONField()
    snapshot = models.ImageField(upload_to="face_enrollment/%Y/%m/", blank=True, null=True, storage=private_storage)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Face template for {self.employee}"


class AttendanceRecord(models.Model):
    STATUSES = [
        ("present", "Present"),
        ("late", "Late"),
        ("half_day", "Half day"),
        ("remote", "Remote"),
        ("absent", "Absent"),
        ("leave", "On leave"),
    ]

    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField(db_index=True)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default="present")

    in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    in_accuracy_m = models.FloatField(null=True, blank=True)
    in_distance_m = models.FloatField(null=True, blank=True)
    in_within_geofence = models.BooleanField(default=False)
    in_face_score = models.FloatField(null=True, blank=True)
    in_snapshot = models.ImageField(upload_to="attendance/%Y/%m/", blank=True, null=True, storage=private_storage)

    out_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    out_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    out_accuracy_m = models.FloatField(null=True, blank=True)
    out_distance_m = models.FloatField(null=True, blank=True)
    out_within_geofence = models.BooleanField(default=False)
    out_face_score = models.FloatField(null=True, blank=True)
    out_snapshot = models.ImageField(upload_to="attendance/%Y/%m/", blank=True, null=True, storage=private_storage)

    office = models.ForeignKey(OfficeLocation, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "employee__employee_code"]
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="one_record_per_day")]

    def __str__(self):
        return f"{self.employee} {self.date}"

    @property
    def worked_hours(self):
        if self.check_in and self.check_out:
            return round((self.check_out - self.check_in).total_seconds() / 3600, 2)
        return None


class AttendanceAttempt(models.Model):
    """Audit log of every punch attempt, successful or not."""

    KINDS = [("enroll", "Enrollment"), ("in", "Check-in"), ("out", "Check-out")]

    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="attendance_attempts")
    kind = models.CharField(max_length=6, choices=KINDS)
    success = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True)
    face_score = models.FloatField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} {self.kind} {'ok' if self.success else 'fail'}"
