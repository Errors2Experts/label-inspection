from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class LipUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'employee_id', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email', 'employee_id')
    fieldsets = UserAdmin.fieldsets + (('LIP', {'fields': ('role', 'phone', 'employee_id')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('LIP', {'fields': ('email', 'role', 'phone', 'employee_id')}),)
