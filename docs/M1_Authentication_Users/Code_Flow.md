# Code Flow - Module 1: Authentication and Users

Format per FDS 27.3: User action -> Frontend -> API -> Backend -> Database -> External -> Response -> UI.
Code lives in `apps/accounts/` (`views.py`, `serializers.py`, `permissions.py`, `models.py`).

## 1. Login
```
User enters username/email + password on Login screen
-> Frontend: GET /api/auth/csrf/ (once) then POST /api/auth/login/ with X-CSRFToken
-> LoginView (csrf_protect) -> LoginSerializer validates fields
-> ScopedRateThrottle ('login', 10/min) -> 429 when exceeded
-> django.contrib.auth.authenticate() -> EmailOrUsernameBackend (backends.py):
     '@' in identifier ? email__iexact : username__iexact   [DB: accounts_user]
     password check; inactive users rejected; dummy hash for unknown users (timing-safe)
-> fail: 401 generic message + warning log
-> ok:   login(request, user) creates session [DB: django_session]
-> Response 200 {user: {id, username, role, ...}}
-> UI: redirect by role to Dashboard / authorised area
```

## 2. Logout
```
Click Logout -> POST /api/auth/logout/ (IsAuthenticated, CSRF) -> logout(request) deletes session -> 200 -> UI returns to Login
```

## 3. Forgot / reset password
```
Forgot Password screen: email
-> POST /api/auth/password-reset/ -> PasswordResetRequestView
-> find active user by email [DB]
-> if found: uid = base64(pk), token = default_token_generator -> send_mail with link   [External: SMTP]
-> ALWAYS 200 'If an account exists...'      (no enumeration)
User opens link -> Reset screen: new password
-> POST /api/auth/password-reset/confirm/ {uid, token, new_password}
-> decode uid, load active user, check token, validate_password()
-> user.set_password() [DB update] (token is tied to the password hash, so it becomes invalid = single use)
-> 200 -> UI: go to Login
```

## 4. Inspector management (Admin)
```
Inspector List -> GET /api/users/?role=&q=&is_active=   (IsAdminOrSupervisor)
Add Inspector  -> POST /api/users/  -> UserCreateSerializer: unique username/email, validate_password -> set_password -> INSERT
Edit Inspector -> PUT/PATCH /api/users/{id}/ (IsAdmin) -> self-protection check -> UserSerializer -> UPDATE
Deactivate     -> DELETE /api/users/{id}/ (IsAdmin) -> is_active=False (row kept) -> 200
Reactivate     -> POST /api/users/{id}/activate/ (IsAdmin)
```

## 5. Profile
```
Profile screen -> GET /api/profile/ -> request.user -> ProfileSerializer
Save           -> PUT/PATCH /api/profile/ -> only first_name, last_name, email, phone writable
Change password-> POST /api/profile/change-password/ -> verify old, validate new, set_password,
                  update_session_auth_hash (stay logged in)
```

## 6. Authorisation on every protected endpoint
```
Request -> SessionAuthentication (+CSRF on unsafe methods) -> permission class
  IsAdmin | IsAdminOrSupervisor | IsAnyRole  (roles_required in permissions.py)
-> 401/403 or view executes
```
Role matrix source: `ROLE_PERMISSION_MATRIX` in `permissions.py`, served by `GET /api/roles/`.
