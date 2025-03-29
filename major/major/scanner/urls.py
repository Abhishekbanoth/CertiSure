from django.urls import path
from .views import upload_folder

urlpatterns = [
    path("upload_folder/", upload_folder, name="upload_folder"),
]
