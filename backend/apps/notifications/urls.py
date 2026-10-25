from django.urls import path

from .views import NotificationListView, NotificationReadView, NotificationSettingsView

urlpatterns = [
    path("settings/notifications", NotificationSettingsView.as_view()),
    path("notifications", NotificationListView.as_view()),
    path("notifications/read-all", NotificationReadView.as_view()),
    path("notifications/<int:pk>/read", NotificationReadView.as_view()),
]
