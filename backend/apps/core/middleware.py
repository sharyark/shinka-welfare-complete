from .context import reset_current_society, set_current_society


class CurrentSocietyMiddleware:
    """
    Sets the current society from the logged-in user for the whole request.

    Session logins (admin panel) are known here. JWT logins (mobile app) are
    authenticated later, inside DRF, so API views also call
    `activate_user_society()` via SocietyScopedMixin.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        society = getattr(user, "society", None) if user and user.is_authenticated else None
        token = set_current_society(society)
        try:
            return self.get_response(request)
        finally:
            reset_current_society(token)
