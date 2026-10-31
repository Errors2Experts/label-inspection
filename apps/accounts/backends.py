from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate with either the username or the (case-insensitive) email address.

    Inactive users are rejected by `ModelBackend.user_can_authenticate`.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        identifier = (username or kwargs.get(user_model.USERNAME_FIELD) or '').strip()
        if not identifier or password is None:
            return None

        lookup = 'email__iexact' if '@' in identifier else 'username__iexact'
        user = user_model.objects.filter(**{lookup: identifier}).first()
        if user is None:
            user_model().set_password(password)  # equalise timing so unknown users are not detectable
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
