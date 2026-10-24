"""Dashboard URL routes."""

from django.urls import path

from apps.dashboard import views

urlpatterns = [
    path("", views.picks, name="picks"),
    path(
        "tomorrow/",
        views.picks_tomorrow,
        name="picks_tomorrow",
    ),
    path(
        "matches/<int:fixture_id>/",
        views.match_detail,
        name="match_detail",
    ),
    path("history/", views.history, name="history"),
]
