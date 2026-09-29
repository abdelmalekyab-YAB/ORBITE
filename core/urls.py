from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("clients/", views.client_list, name="client_list"),
    path("projects/", views.project_list, name="project_list"),
    path("team/", views.team, name="team"),
    path("p/<str:key>/", views.project_detail, name="project_detail"),
    path("p/<str:key>/roadmap/", views.roadmap, name="roadmap"),
    path("p/<str:key>/roadmap/new/", views.milestone_edit, name="milestone_create"),
    path("p/<str:key>/roadmap/<int:pk>/edit/", views.milestone_edit, name="milestone_edit"),
]
