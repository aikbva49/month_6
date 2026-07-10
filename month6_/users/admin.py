from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'phone_number', 'is_staff', 'is_active')
    search_fields = ('email', 'phone_number')
    ordering = ('email',)

admin.site.register(CustomUser, CustomUserAdmin)