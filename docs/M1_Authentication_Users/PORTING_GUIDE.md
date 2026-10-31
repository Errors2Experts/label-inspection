# Porting M1 into the team repository

M1 is self-contained in `apps/accounts/`. Steps once the Tech Lead's project is pushed:

1. **Copy** the whole `apps/accounts/` folder into the team repo (keep the migration `0001_initial.py`).
2. **Before running any migration** in the team repo, add to `settings.py`:
   - `INSTALLED_APPS += ['rest_framework', 'apps.accounts']` (adjust the dotted path if the team uses a different layout and update `name` in `apps/accounts/apps.py` to match)
   - `AUTH_USER_MODEL = 'accounts.User'`  (must be set before the first `migrate`; if the DB was already migrated with the default User, reset the dev DB)
3. Merge these settings from `config/settings.py` (sections are labelled): `AUTH_USER_MODEL`, `AUTHENTICATION_BACKENDS`,
   `LOGIN_URL`, `FRONTEND_RESET_URL`, `AUTH_PASSWORD_VALIDATORS`, session/CSRF cookie settings, the `REST_FRAMEWORK` block
   (session auth, IsAuthenticated default, pagination, throttle rates), the email block (version-aware for Django 6.1 `MAILERS`),
   `LOGGING`, and the test-only fast password hasher.
   Also copy `pyproject.toml` (ruff config) and the email/throttle variables from `.env.example`.
4. Add `path('api/', include('apps.accounts.urls'))` to the root `urls.py`.
5. **Front end:** copy `templates/base.html`, `templates/auth_base.html`, `static/css/lip.css`, `static/js/lip.js` (shared by all modules), then merge the context processor `apps.accounts.context_processors.navigation` into `TEMPLATES[...]['OPTIONS']['context_processors']`, set `LOGIN_URL = '/login/'`, and add `path('', include('apps.accounts.page_urls'))` to the root `urls.py` (before other page routes). Ensure `STATICFILES_DIRS`/`TEMPLATES['DIRS']` point at the project-level `static/` and `templates/` folders. See `Frontend.md`.
6. Copy the docs from `docs/M1_Authentication_Users/`.
7. Run: `python manage.py migrate && python manage.py test apps.accounts` (expect 52 passing), then `python manage.py seed_users` for demo users.
8. Tell teammates to use `from apps.accounts.permissions import IsAdmin, IsAdminOrSupervisor, IsAnyRole` and `settings.AUTH_USER_MODEL`.

Note: DRF `DEFAULT_AUTHENTICATION_CLASSES` = SessionAuthentication (see settings). If the team uses a different auth scheme, tell M1 owner first.

## Code quality checks
`ruff check apps/accounts` and `ruff format --check apps/accounts` must both pass before every commit.
