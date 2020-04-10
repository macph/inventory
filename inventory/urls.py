"""
Inventory URL configuration

"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("item/", views.AddItemView.as_view(), name="item_add"),
    path("item/<str:ident>/", views.item_get, name="item_get"),
    *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
]
