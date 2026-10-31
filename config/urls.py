from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('apps.accounts.page_urls')),  # M1 pages: /login/, /users/, /profile/ ...
    path('', include('apps.catalogue.page_urls')),  # M2 pages: /products/ ...
    path('', include('apps.compliance.page_urls')),  # M4 pages: /rules/ ...
    path('admin/', admin.site.urls),
    path(
        'api/',
        include(
            [
                path('', include('apps.accounts.urls')),  # /api/auth/, /api/users/, /api/profile/
                path('', include('apps.catalogue.urls')),  # /api/products/
                path('', include('apps.compliance.urls')),  # /api/rules/, packs, categories, versions
            ]
        ),
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
