from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.forms import PasswordResetForm


class EmailOrUsernameBackend(ModelBackend):
    """Log in with the e-mail address (what clients know) or the username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            user = get_user_model().objects.filter(email__iexact=username.strip()).order_by("id").first()
            if user is None:
                return None
            username = user.get_username()
        return super().authenticate(request, username=username, password=password, **kwargs)


class OrbitPasswordResetForm(PasswordResetForm):
    """Also send the link to invited people who never chose a password."""

    def get_users(self, email):
        return get_user_model()._default_manager.filter(email__iexact=email, is_active=True)
