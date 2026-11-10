"""
Business rules for trips.

- A family can request the ambulance for itself (from the app); volunteers and the
  office can request for anyone. (The phone call is still fastest; the request
  record is for planning and the log.)
- Volunteers (drivers are volunteers) and the office start and complete trips.
  A vehicle can't be on two trips at once, and must be in service.
- Completing needs the odometer reading; fuel cost is recorded for reports.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role, require_role
from apps.core.exceptions import BusinessRuleError
from apps.registry.models import Household

from .models import Trip, Vehicle

STAFF_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.VOLUNTEER)
S = Trip.Status


@transaction.atomic
def request_trip(*, user, destination: str, household: Household | None = None, **fields) -> Trip:
    if user.society_id is None:
        raise BusinessRuleError("Your account is not linked to a society.")
    is_staff = has_any_role(user, *STAFF_ROLES)
    own_family = household is not None and household.users.filter(pk=user.pk).exists()
    if not is_staff and not (has_any_role(user, Role.BENEFICIARY) and own_family):
        raise BusinessRuleError("You can request the ambulance for your own family only.", code="not_allowed")
    if household is not None and household.society_id != user.society_id:
        raise BusinessRuleError("Household belongs to another society.")
    if not (destination or "").strip():
        raise BusinessRuleError("Say where to go.")
    vehicle = fields.get("vehicle")
    if vehicle is not None and vehicle.society_id != user.society_id:
        raise BusinessRuleError("Vehicle belongs to another society.")
    return Trip.objects.create(
        society_id=user.society_id,
        created_by=user,
        requested_by=user,
        household=household,
        destination=destination.strip(),
        **fields,
    )


def _locked(trip: Trip) -> Trip:
    return Trip.all_objects.select_for_update(of=("self",)).select_related("vehicle").get(pk=trip.pk)


@transaction.atomic
def start_trip(
    trip: Trip, user, *, vehicle: Vehicle | None = None, km_start: int, driver_name: str = ""
) -> Trip:
    require_role(user, *STAFF_ROLES, action="start trips")
    trip = _locked(trip)
    if trip.status != S.REQUESTED:
        raise BusinessRuleError(f"This trip is already {trip.get_status_display().lower()}.")
    vehicle = vehicle or trip.vehicle
    if vehicle is None:
        raise BusinessRuleError("Choose the vehicle.")
    vehicle = Vehicle.all_objects.select_for_update().get(pk=vehicle.pk)  # one trip at a time per vehicle
    if vehicle.society_id != trip.society_id:
        raise BusinessRuleError("Vehicle belongs to another society.")
    if vehicle.status != Vehicle.Status.ACTIVE:
        raise BusinessRuleError(f"{vehicle.name} is not in service.")
    if Trip.all_objects.filter(vehicle=vehicle, status=S.ON_TRIP).exists():
        raise BusinessRuleError(f"{vehicle.name} is already on a trip.", code="vehicle_busy")
    trip.vehicle = vehicle
    trip.km_start = km_start
    trip.driver_name = driver_name or trip.driver_name
    trip.started_at = timezone.now()
    trip.status = S.ON_TRIP
    trip.save()
    return trip


@transaction.atomic
def complete_trip(trip: Trip, user, *, km_end: int, fuel_cost=None, notes: str = "") -> Trip:
    require_role(user, *STAFF_ROLES, action="complete trips")
    trip = _locked(trip)
    if trip.status != S.ON_TRIP:
        raise BusinessRuleError("Only trips on the way can be completed.")
    if km_end < (trip.km_start or 0):
        raise BusinessRuleError("The end reading can't be less than the start reading.")
    trip.km_end = km_end
    trip.fuel_cost = fuel_cost
    trip.notes = "\n".join(filter(None, [trip.notes, notes.strip()]))
    trip.completed_at = timezone.now()
    trip.status = S.COMPLETED
    trip.save()
    return trip


@transaction.atomic
def cancel_trip(trip: Trip, user, reason: str) -> Trip:
    trip = _locked(trip)
    if trip.status not in (S.REQUESTED, S.ON_TRIP):
        raise BusinessRuleError("This trip has already finished.")
    if trip.requested_by_id != user.pk:
        require_role(user, *STAFF_ROLES, action="cancel trips")
    if not (reason or "").strip():
        raise BusinessRuleError("Give a reason.")
    trip.status = S.CANCELLED
    trip.notes = "\n".join(filter(None, [trip.notes, f"Cancelled: {reason.strip()}"]))
    trip.save()
    return trip
