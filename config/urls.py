from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core.backends import OrbitPasswordResetForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # First login: the invited person chooses a password from the link in the invitation e-mail.
    path("welcome/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/welcome.html", post_reset_login=True, success_url="/",
    ), name="welcome"),
    # Forgotten password.
    path("password/forgot/", auth_views.PasswordResetView.as_view(
        form_class=OrbitPasswordResetForm,
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
    ), name="password_reset"),
    path("password/forgot/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        post_reset_login=True, success_url="/",
    ), name="password_reset_confirm"),
    path("password/change/", auth_views.PasswordChangeView.as_view(success_url="/password/change/done/"), name="password_change"),
    path("password/change/done/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("", include("core.urls")),
    path("", include("tickets.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
