from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

DEMO = [
    ('admin1', 'admin1@lip.local', 'admin', 'Demo', 'Admin'),
    ('supervisor1', 'supervisor1@lip.local', 'supervisor', 'Demo', 'Supervisor'),
    ('inspector1', 'inspector1@lip.local', 'inspector', 'Demo', 'Inspector'),
]


class Command(BaseCommand):
    help = 'Create one demo user per role for local development (never run in production).'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='Lip@12345', help='Password for the demo users')

    def handle(self, *args, **opts):
        for username, email, role, first, last in DEMO:
            user, created = User.objects.get_or_create(
                username=username, defaults={'email': email, 'role': role, 'first_name': first, 'last_name': last}
            )
            if created:
                user.set_password(opts['password'])
                user.save()
            self.stdout.write(f'{"created" if created else "exists "} {username} ({role})')
