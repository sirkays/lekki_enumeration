from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path('api/years/',      views.get_available_years, name='get_available_years'),
    
    path("api/properties/",  views.get_properties,   name="get_properties"),

    path("api/capture/bill/",  views.capture_bill,   name="capture_bill"),

    path('api/properties/<str:property_id>/bills/', views.get_property_bills),
    
    path('api/properties/<str:property_id>/comments/', views.property_comments, name='property_comments'),

    path('api/tasks/dashboard/', views.tasks_dashboard, name='tasks_dashboard'),
    
    path('api/app-update/latest/', views.get_latest_update, name='get_latest_update'),
]