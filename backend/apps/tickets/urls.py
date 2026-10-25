from django.urls import path
from rest_framework.routers import SimpleRouter

from .dashboard import ActivityView, CockpitView, TeamView
from .export import TicketExportView
from .views import TicketViewSet, TriageListView

router = SimpleRouter(trailing_slash=False)
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = [path("cockpit", CockpitView.as_view()), path("team", TeamView.as_view()),
               path("activity", ActivityView.as_view()), path("triage", TriageListView.as_view()),
               path("tickets/export.csv", TicketExportView.as_view()), *router.urls]
