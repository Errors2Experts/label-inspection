import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Role
from .permissions import ROLE_PERMISSION_MATRIX, IsAdmin, IsAdminOrSupervisor
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()
logger = logging.getLogger('lip.accounts')

INVALID_CREDENTIALS = 'Invalid username/email or password.'  # never reveal which part was wrong
RESET_REQUESTED = 'If an account exists for this email, a password reset link has been sent.'
RESET_INVALID = 'This password reset link is invalid or has expired.'


# --- Authentication (FR-AUTH-001) -------------------------------------------------


class CSRFView(APIView):
    """GET /api/auth/csrf/ - sets the csrftoken cookie for the front end."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({'csrfToken': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    """POST /api/auth/login/  {identifier, password}  -> session cookie + user/role."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        identifier = ser.validated_data['identifier'].strip()
        password = ser.validated_data['password']

        user = authenticate(request, username=identifier, password=password)
        if user is None:  # also covers inactive accounts (ModelBackend rejects them)
            logger.warning('Failed login attempt')  # identifier deliberately not logged (may be a mistyped password)
            return Response({'detail': INVALID_CREDENTIALS}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)
        logger.info('Login success user=%s role=%s', user.username, user.role)
        return Response({'detail': 'Login successful.', 'user': ProfileSerializer(user).data})


class LogoutView(APIView):
    """POST /api/auth/logout/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info('Logout user=%s', request.user.username)
        logout(request)
        return Response({'detail': 'Logged out.'})


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetRequestView(APIView):
    """POST /api/auth/password-reset/  {email}. Always returns the same message."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=ser.validated_data['email'], is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f'{settings.FRONTEND_RESET_URL}?uid={uid}&token={token}'
            send_mail(
                subject='LIP - password reset',
                message=f'Hello {user.get_username()},\n\nUse this link to reset your password:\n{link}\n\n'
                'If you did not request this, you can ignore this email.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            logger.info('Password reset requested user=%s', user.username)
        return Response({'detail': RESET_REQUESTED})


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset/confirm/  {uid, token, new_password}"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(ser.validated_data['uid'])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({'detail': RESET_INVALID}, status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user, ser.validated_data['token']):
            return Response({'detail': RESET_INVALID}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(ser.validated_data['new_password'], user=user)
        except DjangoValidationError as exc:
            return Response({'new_password': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(ser.validated_data['new_password'])
        user.save(update_fields=['password', 'updated_at'])  # also invalidates the used token
        logger.info('Password reset completed user=%s', user.username)
        return Response({'detail': 'Password has been reset. You can now log in.'})


# --- User / inspector management (FR-AUTH-004) -----------------------------------


class UserViewSet(viewsets.ModelViewSet):
    """/api/users/ - Admin: full access. Supervisor: read-only (FDS 'Limited'). Inspector: none.

    DELETE does not remove the row; it deactivates the account (FR-AUTH-004).
    Filters: ?role=inspector  ?is_active=true  ?q=<username/name/email/employee id>
    """

    queryset = User.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrSupervisor()]
        return [IsAdmin()]

    def get_serializer_class(self):
        return UserCreateSerializer if self.action == 'create' else UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('role') in Role.values:
            qs = qs.filter(role=p['role'])
        if p.get('is_active') in ('true', 'false'):
            qs = qs.filter(is_active=p['is_active'] == 'true')
        q = p.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(employee_id__icontains=q)
            )
        return qs

    def _guard_self(self, request, target, data=None):
        """Stop an admin from locking themselves out."""
        if target.pk != request.user.pk:
            return None
        data = data or {}
        if data.get('is_active') in (False, 'false', 'False', 0) or request.method == 'DELETE':
            return 'You cannot deactivate your own account.'
        if 'role' in data and data['role'] != target.role:
            return 'You cannot change your own role.'
        return None

    def update(self, request, *args, **kwargs):
        error = self._guard_self(request, self.get_object(), request.data)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        error = self._guard_self(request, user)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save(update_fields=['is_active', 'updated_at'])
        logger.info('User deactivated user=%s by=%s', user.username, request.user.username)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=['is_active', 'updated_at'])
        logger.info('User activated user=%s by=%s', user.username, request.user.username)
        return Response(UserSerializer(user).data)


# --- Profile (FR-AUTH-005) --------------------------------------------------------


class ProfileView(APIView):
    """GET/PUT/PATCH /api/profile/ - the logged-in user's own profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        ser = ProfileSerializer(request.user, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class ChangePasswordView(APIView):
    """POST /api/profile/change-password/  {old_password, new_password}"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        request.user.set_password(ser.validated_data['new_password'])
        request.user.save(update_fields=['password', 'updated_at'])
        update_session_auth_hash(request, request.user)  # keep this session logged in
        return Response({'detail': 'Password changed.'})


# --- Roles & permissions screen ---------------------------------------------------


class RoleListView(APIView):
    """GET /api/roles/ - roles plus the FDS 7.2 permission matrix (read-only)."""

    permission_classes = [IsAdminOrSupervisor]

    def get(self, request):
        return Response(
            {
                'roles': [{'value': value, 'label': label} for value, label in Role.choices],
                'matrix': ROLE_PERMISSION_MATRIX,
            }
        )
