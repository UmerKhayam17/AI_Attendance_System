from django.test import TestCase
from rest_framework.exceptions import ValidationError

from organizations.geofence import assert_inside_geofence, distance_m
from organizations.models import Organization


class GeofenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Fence Co", slug="fence-co-gps")
        self.branch = self.org.default_branch()
        self.branch.latitude = 33.6844
        self.branch.longitude = 73.0479
        self.branch.geofence_radius_m = 250
        self.branch.save()

    def test_same_point_is_inside(self):
        result = assert_inside_geofence(self.branch, 33.6844, 73.0479)
        self.assertTrue(result["inside"])
        self.assertLess(result["distance_m"], 5)

    def test_outside_radius_is_rejected(self):
        with self.assertRaises(ValidationError):
            assert_inside_geofence(self.branch, 33.72, 73.12)

    def test_unconfigured_fence_allows_punch(self):
        self.branch.geofence_radius_m = None
        self.branch.save()
        result = assert_inside_geofence(self.branch, 24.86, 67.00)
        self.assertTrue(result["inside"])
        self.assertFalse(result["enabled"])

    def test_haversine_known_distance(self):
        # ~111 km per degree latitude
        meters = distance_m(33.0, 73.0, 34.0, 73.0)
        self.assertGreater(meters, 100_000)
        self.assertLess(meters, 120_000)
