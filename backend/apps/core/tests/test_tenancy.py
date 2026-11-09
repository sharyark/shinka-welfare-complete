import pytest

from apps.core.context import get_current_society, use_society
from apps.core.tests.testapp.models import TenantNote

pytestmark = pytest.mark.django_db


def test_queries_are_filtered_to_the_current_society(society, other_society):
    TenantNote.objects.create(society=society, text="shinka note")
    TenantNote.objects.create(society=other_society, text="other note")

    with use_society(society):
        assert list(TenantNote.objects.values_list("text", flat=True)) == ["shinka note"]

    with use_society(other_society):
        assert list(TenantNote.objects.values_list("text", flat=True)) == ["other note"]


def test_no_society_means_no_filter(society, other_society):
    TenantNote.objects.create(society=society, text="a")
    TenantNote.objects.create(society=other_society, text="b")
    assert TenantNote.objects.count() == 2


def test_all_objects_ignores_the_filter(society, other_society):
    TenantNote.objects.create(society=other_society, text="b")
    with use_society(society):
        assert TenantNote.objects.count() == 0
        assert TenantNote.all_objects.count() == 1


def test_save_fills_society_from_context(society):
    with use_society(society):
        note = TenantNote.objects.create(text="auto")
    assert note.society == society


def test_context_is_restored_after_block(society):
    assert get_current_society() is None
    with use_society(society):
        assert get_current_society() == society
    assert get_current_society() is None
