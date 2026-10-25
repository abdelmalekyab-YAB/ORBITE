from django.urls import path

from .views import (
    InviteAcceptView,
    MeView,
    OrganizationDetailView,
    OrganizationListView,
    PasswordForgotView,
    PasswordResetView,
    ProjectAccessView,
    UserActionView,
    UserDetailView,
    UserListView,
)

urlpatterns = [
    path("me", MeView.as_view()),
    path("auth/invite/accept", InviteAcceptView.as_view()),
    path("auth/password/forgot", PasswordForgotView.as_view()),
    path("auth/password/reset", PasswordResetView.as_view()),
    path("users", UserListView.as_view()),
    path("users/<int:pk>", UserDetailView.as_view()),
    path("users/<int:pk>/project-access", ProjectAccessView.as_view()),
    path("users/<int:pk>/<str:action>", UserActionView.as_view()),
    path("organizations", OrganizationListView.as_view()),
    path("organizations/<int:pk>", OrganizationDetailView.as_view()),
]
