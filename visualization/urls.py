from django.urls import path
from . import views

app_name = "visualization"

urlpatterns = [
    path("", views.user_login, name="user_login"),
    path("logout/", views.user_logout, name="user_logout"),
    path("visualization/", views.visualization, name="visualization"),
    path("api/properties/", views.api_properties, name="api_properties"),
    path("api/chart-data/", views.api_chart_data, name="api_chart_data"),

    path("api/test-data/", views.test_set, name="test_set"),

    path("export/properties/", views.export_properties_excel, name="export_properties_excel"),
]