from django.urls import path

from . import manage_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("clients/", views.client_list, name="client_list"),
    path("projects/", views.project_list, name="project_list"),
    path("team/", views.team, name="team"),
    path("clients/new/", manage_views.company_edit, name="company_create"),
    path("clients/<int:pk>/", manage_views.company_detail, name="company_detail"),
    path("clients/<int:pk>/edit/", manage_views.company_edit, name="company_edit"),
    path("projects/new/", manage_views.project_edit, name="project_create"),
    path("p/<str:key>/settings/", manage_views.project_edit, name="project_settings"),
    path("accounts/", manage_views.user_list, name="user_list"),
    path("accounts/tab/<str:tab>/", manage_views.user_list, name="user_list_tab"),
    path("accounts/new/", manage_views.user_edit, name="user_create"),
    path("accounts/<int:pk>/", manage_views.user_edit, name="user_edit"),
    path("accounts/<int:pk>/invite/", manage_views.user_invite_again, name="user_invite_again"),
    path("accounts/<int:pk>/toggle/", manage_views.user_toggle_active, name="user_toggle_active"),
    path("p/<str:key>/", views.project_detail, name="project_detail"),
    path("p/<str:key>/roadmap/", views.roadmap, name="roadmap"),
    path("p/<str:key>/roadmap/new/", views.milestone_edit, name="milestone_create"),
    path("p/<str:key>/roadmap/<int:pk>/edit/", views.milestone_edit, name="milestone_edit"),
]
