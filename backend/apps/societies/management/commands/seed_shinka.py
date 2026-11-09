"""
Create the Shinka Welfare Society record. Safe to run more than once.

    python manage.py seed_shinka
"""

from django.core.management.base import BaseCommand

from apps.societies.models import Society


class Command(BaseCommand):
    help = "Create the Shinka Welfare Society (tenant) if it doesn't exist."

    def handle(self, *args, **options):
        society, created = Society.objects.get_or_create(
            slug="shinka",
            defaults={
                "name": "Shinka Welfare Society",
                "phone": "+923009786788",
                "address": "Village Shinka, Hazro, Attock",
                "website": "https://www.shinkawelfaresociety.com",
                "founded_year": 2019,
            },
        )
        verb = "Created" if created else "Already exists:"
        self.stdout.write(self.style.SUCCESS(f"{verb} {society}"))
