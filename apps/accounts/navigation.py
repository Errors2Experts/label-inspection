"""Sidebar definition shared by every module (FDS 8). `ready=False` items show a "coming soon" toast
until their module ships - flip the flag when the module's pages exist."""

from .models import Role

ALL = (Role.ADMIN, Role.SUPERVISOR, Role.INSPECTOR)
STAFF = (Role.ADMIN, Role.SUPERVISOR)

NAV_ITEMS = [
    {'key': 'dashboard', 'label': 'Dashboard', 'icon': '📊', 'url': '/dashboard/', 'roles': ALL, 'ready': True},
    {
        'key': 'inspection',
        'label': 'New Inspection',
        'icon': '🔍',
        'url': '/inspections/new/',
        'roles': ALL,
        'ready': False,
    },
    {'key': 'history', 'label': 'History & Evidence', 'icon': '📋', 'url': '/history/', 'roles': ALL, 'ready': False},
    {'key': 'catalogue', 'label': 'Product Catalogue', 'icon': '📦', 'url': '/products/', 'roles': ALL, 'ready': True},
    {'key': 'rules', 'label': 'Compliance Rules', 'icon': '⚖️', 'url': '/rules/', 'roles': STAFF, 'ready': True},
    {'key': 'reports', 'label': 'Reports', 'icon': '📄', 'url': '/reports/', 'roles': ALL, 'ready': False},
    {'section': 'Administration', 'roles': STAFF},
    {'key': 'users', 'label': 'Inspectors', 'icon': '👥', 'url': '/users/', 'roles': STAFF, 'ready': True},
    {'key': 'roles', 'label': 'Roles & Permissions', 'icon': '🔐', 'url': '/roles/', 'roles': STAFF, 'ready': True},
]


def nav_for(role, path):
    """Return the menu items visible to `role`, flagging the active one by URL prefix."""
    items = []
    for item in NAV_ITEMS:
        if role not in item['roles']:
            continue
        entry = dict(item)
        entry['active'] = 'url' in item and path.startswith(item['url'])
        items.append(entry)
    return items
