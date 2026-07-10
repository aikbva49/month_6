import redis
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def generate_user_products_report(user_id):
    try:
        user = User.objects.get(id=user_id)
        user_products = user.products.all() 
        total_spent = sum([prod.price for prod in user_products])
        
        print(f" [Celery] Отчет для {user.email} успешно создан. Всего товаров: {user_products.count()}, на сумму {total_spent} ")
        return True
    except User.DoesNotExist:
        return False

@shared_task
def clear_expired_redis_codes():
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
    keys = r.keys("confirm_code:*")
    print(f"[Celery Beat Crontab] Проверка кэша в полночь. Найдено активных кодов в памяти: {len(keys)}")
    return f"Checked {len(keys)} keys."


@shared_task
def send_welcome_email_task(user_email, first_name):
    subject = "Добро пожаловать в наш Магазин!"
    message = f"Привет, {first_name if first_name else 'пользователь'}!\n\nСпасибо, что зарегистрировались на нашей платформе."
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [user_email]
    
    send_mail(subject, message, from_email, recipient_list, fail_silently=False)
    print(f" [Celery SMTP] Письмо успешно отправлено на {user_email}")
    return "Email sent."