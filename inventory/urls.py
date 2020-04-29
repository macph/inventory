"""
Inventory URL configuration

"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("records/", views.records, name="records"),
    path("records/<str:ident>/", views.records, name="item_records"),
    path("item/", views.AddItem.as_view(), name="item_add"),
    path("item/<str:ident>/", views.GetItem.as_view(), name="item_get"),
    path("item/<str:ident>/delete/", views.DeleteItem.as_view(), name="item_delete"),
    path("item/<str:ident>/record/", views.AddRecord.as_view(), name="record_add"),
    path("update/", views.Update.as_view(), name="update"),
    *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
]
