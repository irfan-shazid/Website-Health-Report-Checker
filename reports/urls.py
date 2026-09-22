from django.conf import settings
from django.urls import path

from reports import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sign-in/", views.SignInView.as_view(), name="login"),
    path("sign-out/", views.SignOutView.as_view(), name="logout"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("favicon.ico", views.favicon, name="favicon"),
]

if settings.DEBUG:
    urlpatterns.append(path("styleguide/", views.styleguide, name="styleguide"))
