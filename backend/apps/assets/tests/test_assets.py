import pytest
from django.test import Client

from apps.assets.models import Asset
from apps.registry.tests.conftest import *  # noqa: F403

pytestmark = pytest.mark.django_db


def test_status_changes_are_kept_in_history(society, coordinator):
    asset = Asset.objects.create(society=society, kind="water_bore", name="Bore near masjid")
    client = Client()
    client.force_login(coordinator)
    client.post("/admin/assets/asset/", {"action": "mark_needs_repair", "_selected_action": [asset.pk]})
    client.post("/admin/assets/asset/", {"action": "mark_working", "_selected_action": [asset.pk]})
    statuses = [h.status for h in asset.history.order_by("history_date")]
    assert statuses == ["working", "needs_repair", "working"]
    assert asset.history.latest().history_user == coordinator


@pytest.mark.parametrize("path", ["asset/", "asset/add/"])
def test_admin_pages(coordinator, path):
    client = Client()
    client.force_login(coordinator)
    assert client.get(f"/admin/assets/{path}").status_code == 200


def test_add_asset_in_admin(coordinator, society, mohalla):
    client = Client()
    client.force_login(coordinator)
    response = client.post(
        "/admin/assets/asset/add/",
        {"kind": "streetlight", "name": "Light at the chowk", "mohalla": mohalla.pk, "status": "working"},
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    assert Asset.all_objects.get().society == society
