import random
import requests
import redis  
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, LoginSerializer
from .tasks import send_welcome_email_task, generate_user_products_report  

User = get_user_model()

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

class RegisterAPIView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save() 
        user.is_active = False
        user.save()

        confirmation_code = str(random.randint(100000, 999999))
        redis_key = f"confirm_code:{user.email}"
        redis_client.setex(redis_key, 300, confirmation_code)
        
        print(f"\nСгенерированный код для {user.email}: {confirmation_code} \n")
        
        send_welcome_email_task.delay(user.email, user.first_name)
        
        generate_user_products_report.delay(user.id)
        
        return Response(
            {
                "message": "Пользователь успешно зарегистрирован. Код подтверждения отправлен, задачи Celery запущены.", 
                "email": user.email
            },
            status=status.HTTP_201_CREATED
        )


class VerifyCodeAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        
        if not email or not code:
            return Response({"error": "Email и код обязательны."}, status=status.HTTP_400_BAD_REQUEST)
            
        redis_key = f"confirm_code:{email}"
        saved_code = redis_client.get(redis_key)
        
        if not saved_code:
            return Response({"error": "Код не найден или его срок действия истек."}, status=status.HTTP_400_BAD_REQUEST)
            
        if saved_code != str(code):
            return Response({"error": "Неверный код подтверждения."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(email=email)
            user.is_active = True  
            user.save()
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)
            
        redis_client.delete(redis_key)
        
        return Response({"message": "Аккаунт успешно подтвержден!"}, status=status.HTTP_200_OK)


class LoginAPIView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get('email')
        password = serializer.validated_data.get('password')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Неверный email или пароль"}, status=status.HTTP_400_BAD_REQUEST)
            
        if not user.check_password(password):
            return Response({"error": "Неверный email или пароль"}, status=status.HTTP_400_BAD_REQUEST)
            
        if not user.is_active:
            return Response({"error": "Ваш аккаунт не подтвержден. Введите код подтверждения."}, status=status.HTTP_403_FORBIDDEN)
            
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)
    

class GoogleAuthAPIView(APIView):
    def get(self, request):
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={settings.GOOGLE_CLIENT_ID}&"
            f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email&"
            f"access_type=offline"
        )
        return Response({"auth_url": auth_url}, status=status.HTTP_200_OK)


class GoogleCallbackAPIView(APIView):
    def get(self, request):
        code = request.GET.get('code')
        if not code:
            return Response({"error": "Code missing from Google redirect"}, status=status.HTTP_400_BAD_REQUEST)

        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        
        token_response = requests.post(token_url, data=token_data).json()
        access_token = token_response.get('access_token')

        if not access_token:
            return Response({"error": "Failed to obtain access token", "details": token_response}, status=status.HTTP_400_BAD_REQUEST)

        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info = requests.get(user_info_url, headers=headers).json()

        email = user_info.get('email')
        given_name = user_info.get('given_name')    
        family_name = user_info.get('family_name')  

        if not email:
            return Response({"error": "Email not provided by Google"}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': given_name,
                'last_name': family_name,
                'registration_source': 'google',
                'is_active': True,  
            }
        )

        if not created:
            user.first_name = given_name
            user.last_name = family_name
            user.is_active = True  
            user.save()

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        refresh = RefreshToken.for_user(user)
        
        return Response({
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "registration_source": user.registration_source
            },
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)