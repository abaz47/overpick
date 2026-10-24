"""Dashboard URL routes."""

from django.urls import path

from apps.dashboard import views

urlpatterns = [
    path("", views.upcoming, name="upcoming"),
    path(
        "matches/<int:fixture_id>/",
        views.match_detail,
        name="match_detail",
    ),
    path("history/", views.history, name="history"),
    path("leagues/", views.leagues, name="leagues"),
]
