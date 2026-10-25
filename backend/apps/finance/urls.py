from django.urls import path

from .views import (
    FinanceExportView,
    InstallmentDetailView,
    InstallmentListView,
    OverviewView,
    ProjectFinanceView,
    QuoteInstallmentView,
    SettingsView,
    StaffView,
)

urlpatterns = [
    path("finance/overview", OverviewView.as_view()),
    path("finance/export.csv", FinanceExportView.as_view()),
    path("finance/projects/<str:key>", ProjectFinanceView.as_view()),
    path("finance/projects/<str:key>/installments", InstallmentListView.as_view()),
    path("finance/projects/<str:key>/installments/<int:pk>", InstallmentDetailView.as_view()),
    path("finance/quotes/<int:quote_id>/installments/<int:pk>", QuoteInstallmentView.as_view()),
    path("finance/staff", StaffView.as_view()),
    path("finance/settings", SettingsView.as_view()),
]
