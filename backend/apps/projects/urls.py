from django.urls import path

from .views import (
    MilestoneDetailView,
    MilestoneListView,
    ProjectArchiveView,
    ProjectDetailView,
    ProjectListView,
    WorkflowResetView,
    WorkflowView,
)

urlpatterns = [
    path("projects", ProjectListView.as_view()),
    path("projects/<str:key>", ProjectDetailView.as_view()),
    path("projects/<str:key>/milestones", MilestoneListView.as_view()),
    path("projects/<str:key>/milestones/<int:pk>", MilestoneDetailView.as_view()),
    path("projects/<str:key>/archive", ProjectArchiveView.as_view(), {"action": "archive"}),
    path("projects/<str:key>/unarchive", ProjectArchiveView.as_view(), {"action": "unarchive"}),
    path("workflow", WorkflowView.as_view()),
    path("workflow/reset", WorkflowResetView.as_view()),
]
