"""
Create the Shinka Welfare Society, its funds and chart of accounts.
Safe to run more than once.

    python manage.py seed_shinka
"""

from django.core.management.base import BaseCommand

from apps.finance.services.setup import ensure_finance_setup
from apps.societies.models import Society


class Command(BaseCommand):
    help = "Create the Shinka Welfare Society (tenant), its funds and chart of accounts."

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
        if not society.settings.get("household_code_prefix"):
            society.settings["household_code_prefix"] = "SHK"  # household codes: SHK-0001, SHK-0002…
            society.save(update_fields=["settings", "updated_at"])
        verb = "Created" if created else "Already exists:"
        self.stdout.write(self.style.SUCCESS(f"{verb} {society}"))
        ensure_finance_setup(society)
        self.stdout.write(self.style.SUCCESS("Funds and accounts ready."))
