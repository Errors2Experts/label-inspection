"""Server-rendered pages for Module 1. Data is loaded by the page scripts through the REST API;
these views only enforce login / role and render the template shell."""

from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import RedirectView, TemplateView

from .models import Role

ADMIN_ONLY = (Role.ADMIN,)
STAFF = (Role.ADMIN, Role.SUPERVISOR)


@method_decorator(ensure_csrf_cookie, name='dispatch')  # JS reads the csrftoken cookie for API calls
class PageView(TemplateView):
    """Base page: `public` pages need no login; otherwise `roles` (None = any role) is enforced."""

    public = False
    roles = None

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if self.public:
            if user.is_authenticated and getattr(self, 'redirect_if_authenticated', False):
                return redirect('page-dashboard')
        elif not user.is_authenticated:
            return redirect(f'{settings.LOGIN_URL}?next={quote(request.get_full_path())}')
        elif self.roles and user.role not in self.roles:
            return render(request, 'accounts/forbidden.html', status=403)
        return super().dispatch(request, *args, **kwargs)


class LoginPage(PageView):
    template_name = 'accounts/login.html'
    public = True
    redirect_if_authenticated = True


class ForgotPasswordPage(PageView):
    template_name = 'accounts/forgot_password.html'
    public = True


class ResetPasswordPage(PageView):
    template_name = 'accounts/reset_password.html'
    public = True


class DashboardPage(PageView):
    """Placeholder landing page; Module 7 replaces it with the real dashboard."""

    template_name = 'accounts/dashboard.html'


class UserListPage(PageView):
    template_name = 'accounts/user_list.html'
    roles = STAFF


class UserFormPage(PageView):
    """Add (mode='add') and Edit (mode='edit') Inspector - admin only."""

    template_name = 'accounts/user_form.html'
    roles = ADMIN_ONLY
    mode = 'add'

    def get_context_data(self, **kwargs):
        return super().get_context_data(mode=self.mode, **kwargs)


class UserDetailPage(PageView):
    template_name = 'accounts/user_detail.html'
    roles = STAFF


class RolesPage(PageView):
    template_name = 'accounts/roles.html'
    roles = STAFF


class ProfilePage(PageView):
    template_name = 'accounts/profile.html'


class HomeRedirect(RedirectView):
    pattern_name = 'page-dashboard'
