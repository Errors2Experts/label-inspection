from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    SUPERVISOR = 'supervisor', 'Supervisor'
    INSPECTOR = 'inspector', 'Inspector'


class User(AbstractUser):
    """Single user table for Admin / Supervisor / Inspector (FDS section 7, 9.5).

    Role is stored on the user; other modules should import
    `apps.accounts.permissions` instead of checking the field directly.
    Accounts are deactivated (is_active=False), never hard-deleted, so
    inspection history and audit records stay intact.
    """

    email = models.EmailField('email address', unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.INSPECTOR)
    phone = models.CharField(max_length=20, blank=True)
    employee_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['username']

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        if self.employee_id == '':
            self.employee_id = None  # keep NULLs so the unique constraint allows many blanks
        if self.is_superuser:
            self.role = Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.get_full_name().strip() or self.username

    @property
    def initials(self):
        parts = self.get_full_name().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return (parts[0] if parts else self.username)[:2].upper()

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN

    @property
    def is_supervisor_role(self):
        return self.role == Role.SUPERVISOR

    @property
    def is_inspector_role(self):
        return self.role == Role.INSPECTOR

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'
