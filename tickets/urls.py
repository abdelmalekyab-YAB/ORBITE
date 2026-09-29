from django.urls import path

from . import views

urlpatterns = [
    path("tickets/", views.all_tickets, name="all_tickets"),
    path("attachments/<int:pk>/", views.attachment_download, name="attachment_download"),
    path("p/<str:key>/tickets/", views.project_tickets, name="project_tickets"),
    path("p/<str:key>/tickets/new/", views.ticket_create, name="ticket_create"),
    path("p/<str:key>/tickets/<int:number>/", views.ticket_detail, name="ticket_detail"),
    path("p/<str:key>/tickets/<int:number>/edit/", views.ticket_edit, name="ticket_edit"),
]
