from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Site Health Report administration"
admin.site.site_title = "Site Health Report"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("reports.urls")),
]
