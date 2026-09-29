"""Haversine distance and branch geofence checks for mobile camera punches."""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from rest_framework.exceptions import ValidationError


def distance_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = radians(float(lat1)), radians(float(lat2))
    dlat = p2 - p1
    dlon = radians(float(lon2) - float(lon1))
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(min(1.0, a)))


def geofence_status(branch) -> dict:
    if branch is None:
        return {"enabled": False, "latitude": None, "longitude": None, "radius_m": None, "branch_name": ""}
    lat = branch.latitude
    lng = branch.longitude
    radius = branch.geofence_radius_m
    enabled = lat is not None and lng is not None and bool(radius)
    return {
        "enabled": enabled,
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lng) if lng is not None else None,
        "radius_m": int(radius) if radius else None,
        "branch_name": branch.name,
    }


def assert_inside_geofence(branch, latitude, longitude) -> dict:
    status = geofence_status(branch)
    if latitude is None or longitude is None:
        raise ValidationError({"location": "Phone location is required for camera punch"})
    if not status["enabled"]:
        return {**status, "distance_m": None, "inside": True}
    dist = distance_m(latitude, longitude, status["latitude"], status["longitude"])
    inside = dist <= status["radius_m"]
    if not inside:
        raise ValidationError({
            "location": (
                f"You are {int(dist)} m from {status['branch_name']}. "
                f"Punch is allowed within {status['radius_m']} m."
            )
        })
    return {**status, "distance_m": round(dist, 1), "inside": True}
