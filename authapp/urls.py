from django.urls import path
from . import views

app_name = "authapp"

urlpatterns = [
    path("api/signin/",  views.signin,   name="signin"),
    path('api/me/', views.current_user_profile, name='current_user_profile'),
    path('api/me/upload-profile-image/', views.upload_profile_image, name='upload_profile_image'),
]