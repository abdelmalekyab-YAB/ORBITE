from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("profiles", views.BillingProfileViewSet, basename="finance-profile")
router.register("invoices", views.InvoiceViewSet, basename="finance-invoice")
router.register("fixed", views.FixedOccurrenceViewSet, basename="finance-fixed")
router.register("expenses", views.ExpenseViewSet, basename="finance-expense")

urlpatterns = [
    path("dashboard/", views.dashboard),
    path("month/<str:month>/", views.month_view),
    path("upcoming/", views.upcoming),
    path("recap/", views.recap),
    path("export/accounting/", views.export_accounting),
    path("export/ceo.pdf", views.export_ceo_pdf),
    path("zoho/sync/", views.zoho_sync),
    path("orbit-projects/", views.orbit_projects),
    path("", include(router.urls)),
]
