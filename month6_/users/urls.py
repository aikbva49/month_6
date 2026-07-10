from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterAPIView.as_view(), name='user_register'),
    path('login/', views.LoginAPIView.as_view(), name='user_login'),

    path('google/', views.GoogleAuthAPIView.as_view(), name='google_auth'),
    path('google/callback/', views.GoogleCallbackAPIView.as_view(), name='google_callback'),

    path('verify/', views.VerifyCodeAPIView.as_view(), name='user_verify'),  
]