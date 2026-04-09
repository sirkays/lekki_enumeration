from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("api/properties/",  views.get_properties,   name="get_properties"),

    path("api/capture/bill/",  views.capture_bill,   name="capture_bill"),

    path('api/properties/<str:property_id>/bills/', views.get_property_bills),

    path('api/tasks/dashboard/', views.tasks_dashboard, name='tasks_dashboard'),
    
]