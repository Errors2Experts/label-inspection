# Front End - Module 1: Authentication and Users

Stack (FDS 5): Django templates + HTML5 / CSS3 / vanilla JavaScript, calling the DRF API with session cookies and the CSRF token.

## Screens and routes
| FDS screen | Route | Roles | Template | API used |
|---|---|---|---|---|
| Login | `/login/` | public | `login.html` | POST /api/auth/login/ |
| Forgot Password | `/forgot-password/` | public | `forgot_password.html` | POST /api/auth/password-reset/ |
| Reset Password (email link) | `/reset-password/?uid=&token=` | public | `reset_password.html` | POST /api/auth/password-reset/confirm/ |
| Inspector List | `/users/` | Admin, Supervisor (read-only) | `user_list.html` | GET /api/users/ (search, role, status filters, paging), DELETE / activate |
| Add Inspector | `/users/add/` | Admin | `user_form.html` | POST /api/users/ |
| Inspector Details | `/users/<id>/` | Admin, Supervisor | `user_detail.html` | GET /api/users/{id}/ |
| Edit Inspector | `/users/<id>/edit/` | Admin | `user_form.html` | GET, PATCH /api/users/{id}/ |
| Roles and Permissions | `/roles/` | Admin, Supervisor | `roles.html` | GET /api/roles/ |
| User Profile | `/profile/` | all | `profile.html` | GET/PATCH /api/profile/, POST /api/profile/change-password/ |
| Dashboard (placeholder until Module 7) | `/dashboard/` | all | `dashboard.html` | - |

Unauthenticated visits redirect to `/login/?next=...`; a role without access gets a 403 "Access denied" page. The sidebar is built server-side per role (`apps/accounts/navigation.py`); links for modules not yet delivered show an "upcoming module" toast - set `ready: True` in `NAV_ITEMS` when a module's pages exist.

## Files
- Shared (all modules): `templates/base.html`, `templates/auth_base.html`, `static/css/lip.css`, `static/js/lip.js` (API client, toasts, confirm dialog, error display, menu).
- M1 only: `apps/accounts/templates/accounts/*.html`, `apps/accounts/static/accounts/js/{auth,users,account}.js`, `page_views.py`, `page_urls.py`, `navigation.py`, `context_processors.py`.

## Design tokens (sampled from the approved demo screens)
Primary teal `#0f766e` (buttons, logo, active step), active nav `#f0fdfa`, page `#f8fafc`, cards white with `#e2e8f0` border and 12px radius, status pills green `#dcfce7/#15803d`, red `#fee2e2/#b91c1c`, amber `#fef3c7/#92400e`, sidebar with emoji nav icons, top bar with page title + action button + avatar/name, sidebar footer with name and role. Responsive: sidebar collapses behind a menu button under 900px.

## Manual UI test checklist (to run in a browser; automated coverage is for routing, access and API only)
| ID | Check | Expected |
|---|---|---|
| M1-UI-01 | Open /login/ and compare with demo styling | Teal brand, card layout, matching fonts/colours |
| M1-UI-02 | Wrong password / empty fields | Inline red banner; no account-existence hint |
| M1-UI-03 | Valid login (each role) | Redirect to /dashboard/ (or `next`); sidebar matches role |
| M1-UI-04 | Forgot password, then follow link from console email | Generic success message; reset page sets new password; login works |
| M1-UI-05 | Inspector list search / role / status filters / paging | Table updates; counts correct |
| M1-UI-06 | Add inspector with errors (dup username, weak password, mismatch) | Field-level messages under inputs |
| M1-UI-07 | Edit inspector; deactivate then activate with confirm dialog | Status pill updates; toast shown |
| M1-UI-08 | Supervisor opens list / details | No Add/Edit/Deactivate buttons |
| M1-UI-09 | Inspector opens /users/ or /roles/ | "Access denied" page |
| M1-UI-10 | Profile update and change password | Toast; name/initials refresh in layout |
| M1-UI-11 | Resize below 900px | Sidebar hidden; menu button toggles it; forms single column |
| M1-UI-12 | Sign out from avatar menu and sidebar | Back at /login/; back button does not show protected data |
