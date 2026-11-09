"""
Role checks used by service functions.

Note: being a superuser does NOT bypass these checks. Money decisions must be
made by real office bearers, never by the developer account.
"""

from django.core.exceptions import PermissionDenied

from .models import Role

# Everyone who works for the society (not beneficiaries, not read-only auditors).
MEMBER_ROLES = (Role.PRESIDENT, Role.FINANCE_SECRETARY, Role.PROGRAM_COORDINATOR, Role.VOLUNTEER)
OFFICE_ROLES = (Role.PRESIDENT, Role.FINANCE_SECRETARY, Role.PROGRAM_COORDINATOR, Role.AUDITOR)


def user_roles(user) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    return set(user.groups.values_list("name", flat=True))


def has_any_role(user, *roles: str) -> bool:
    return bool(user_roles(user) & set(roles))


def require_role(user, *roles: str, action: str = "do this") -> None:
    if not has_any_role(user, *roles):
        allowed = ", ".join(roles)
        raise PermissionDenied(f"Only {allowed} can {action}.")
