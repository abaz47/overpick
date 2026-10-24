"""URL routes for the core app."""

from django.urls import path

from apps.core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
]
