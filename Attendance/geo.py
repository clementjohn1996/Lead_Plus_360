import math

from django.conf import settings

from .models import OfficeLocation


def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6371000.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = p2 - p1
    dlmb = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def parse_coords(lat, lng, accuracy):
    """Validate browser-supplied coordinates; returns floats or raises ValueError."""
    try:
        lat, lng = float(lat), float(lng)
        accuracy = float(accuracy) if accuracy not in (None, "") else None
    except (TypeError, ValueError):
        raise ValueError("Location is missing. Allow location access and try again.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or math.isnan(lat) or math.isnan(lng):
        raise ValueError("Location is invalid.")
    return lat, lng, accuracy


def nearest_office(lat, lng):
    """Return (office, distance_m, inside) for the closest active office."""
    best = None
    for office in OfficeLocation.objects.filter(is_active=True):
        distance = haversine_m(lat, lng, office.latitude, office.longitude)
        if best is None or distance < best[1]:
            best = (office, distance)
    if best is None:
        return None, None, False
    office, distance = best
    return office, distance, distance <= office.radius_m


def accuracy_ok(accuracy):
    return accuracy is not None and accuracy <= settings.GEO_MAX_ACCURACY_M
