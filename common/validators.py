from datetime import date
from rest_framework.exceptions import ValidationError

def validate_user_age_from_token(birthdate_str):
    if not birthdate_str or birthdate_str == 'None':
        raise ValidationError("Укажите дату рождения, чтобы создать продукт.")

    try:
        birth_date = date.fromisoformat(birthdate_str)
    except (ValueError, TypeError):
        raise ValidationError("Некорректный формат даты рождения в токене.")

    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    if age < 18:
        raise ValidationError("Вам должно быть 18 лет, чтобы создать продукт.")