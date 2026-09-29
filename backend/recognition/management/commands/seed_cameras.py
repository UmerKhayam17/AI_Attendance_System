from django.core.management.base import BaseCommand, CommandError

from organizations.models import Organization
from recognition.models import Camera


class Command(BaseCommand):
    help = "Add one RTSP camera to an organization (does not seed shared credentials)"

    def add_arguments(self, parser):
        parser.add_argument("--org", required=True, help="Organization slug")
        parser.add_argument("--name", required=True)
        parser.add_argument("--rtsp", required=True)
        parser.add_argument("--location", default="")
        parser.add_argument("--sort", type=int, default=0)
        parser.add_argument(
            "--zone",
            default="mixed",
            choices=["mixed", "entry", "exit", "interior"],
        )

    def handle(self, *args, **options):
        org = Organization.objects.filter(slug=options["org"]).first()
        if not org:
            raise CommandError(f"Organization '{options['org']}' not found")

        obj, created = Camera.objects.update_or_create(
            organization=org,
            name=options["name"],
            defaults={
                "rtsp_url": options["rtsp"],
                "location": options["location"],
                "sort_order": options["sort"],
                "zone": options["zone"],
                "is_active": True,
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb}: {obj.name} for {org.slug}"))
