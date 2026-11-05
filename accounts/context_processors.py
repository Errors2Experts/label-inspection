from .navigation import nav_for


def navigation(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    return {
        'nav_items': nav_for(user.role, request.path),
        'lip_user': {'id': user.pk, 'username': user.username, 'role': user.role, 'fullName': user.full_name},
    }
