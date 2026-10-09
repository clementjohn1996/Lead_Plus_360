from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "LeadPlus-360 Administration"
admin.site.site_title = "LeadPlus-360"
admin.site.index_title = "Company settings"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("crm/", include("LeadManager.urls")),
    path("hr/", include("HR.urls")),
    path("attendance/", include("Attendance.urls")),
    path("performance/", include("Performance.urls")),
    path("delivery/", include("Delivery.urls")),
    path("accounts/", include("Accounts.urls")),
    path("tv/", include("Performance.tv_urls")),
    path("", include("Control.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
