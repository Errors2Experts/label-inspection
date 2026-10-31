# Impact Analysis - Module 1: Authentication and Users

| Item | Detail |
|---|---|
| Developer | Manishashri P |
| Window | 05/10/2026 - 15/10/2026 |
| Status | Draft |

## 1. New functionality
Login/logout, password reset, user (inspector) CRUD with deactivate/reactivate, own-profile view/update, change password, roles & permissions matrix, reusable RBAC permission classes, `seed_users` command for dev.

## 2. Existing functionality affected
None - this is the foundation module. **Every other module depends on it** (user identity and roles).

## 3. Database impact
| Change | Detail |
|---|---|
| Table `accounts_user` | Custom user model extending `AbstractUser` + `role`, `phone`, `employee_id` (unique, nullable), `created_at`, `updated_at`; `email` made unique |
| `AUTH_USER_MODEL = 'accounts.User'` | **Must be set before the first migration of any app.** Changing it later requires resetting migrations |
| Roles | Stored as a field (Admin/Supervisor/Inspector), not Django groups - simpler and matches FDS 7.2 |
| Deletion | Users are deactivated, never deleted, so inspections/audit rows keep a valid FK |

## 4. API impact
| Endpoint | Method | Access |
|---|---|---|
| /api/auth/csrf/ | GET | Public |
| /api/auth/login/ | POST | Public (CSRF-protected) |
| /api/auth/logout/ | POST | Authenticated |
| /api/auth/password-reset/ | POST | Public |
| /api/auth/password-reset/confirm/ | POST | Public |
| /api/users/ , /api/users/{id}/ | GET, POST, PUT, PATCH, DELETE(=deactivate) | Admin full; Supervisor read-only |
| /api/users/{id}/activate/ | POST | Admin |
| /api/profile/ | GET, PUT, PATCH | Authenticated (own) |
| /api/profile/change-password/ | POST | Authenticated |
| /api/roles/ | GET | Admin, Supervisor |

Added beyond the FDS list: `csrf`, `password-reset/confirm`, `activate`, `change-password`, `roles` (needed to make the listed screens and flows work).

## 5. UI impact
Screens: Login, Forgot Password (+ reset-confirm page), Inspector List, Add Inspector, Inspector Details, Edit Inspector, Roles and Permissions, User Profile. Front end must send the CSRF token header (`X-CSRFToken`) on POSTs and use session cookies.

## 6. Integration impact
| Module | What it needs from M1 |
|---|---|
| M2 Catalogue | `IsAnyRole` for read, role checks for write |
| M3 Inspection | `request.user` bound to inspection as inspector |
| M4 Compliance | `IsAdminOrSupervisor` on rule management |
| M5 History/Audit | `AUTH_USER_MODEL` FK for AuditLog.actor; M1 currently logs to the `lip.accounts` logger, to be switched to AuditLog once M5 exists |
| M6/M7 | Role-based visibility |

Import pattern: `from apps.accounts.permissions import IsAdmin, IsAdminOrSupervisor, IsAnyRole` and `settings.AUTH_USER_MODEL`.

## 6a. Project-wide settings introduced by M1 (shared with all modules)
| Setting | Effect on other modules |
|---|---|
| `AUTH_USER_MODEL`, `AUTHENTICATION_BACKENDS` | All FKs to users must use `settings.AUTH_USER_MODEL`; login accepts username or email |
| `REST_FRAMEWORK` default auth = Session, default permission = IsAuthenticated | New endpoints are protected by default - public ones must opt out explicitly |
| `REST_FRAMEWORK` default pagination (page size 20) | List endpoints return `{count, next, previous, results}` |
| `DEFAULT_THROTTLE_RATES` (`login`, `password_reset`) | Only applies to views using those scopes |

## 7. Dependencies
Django, DRF, PostgreSQL, SMTP server (reset emails; console backend in dev).

## 8. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Custom user model set late | Done first, before any other migration |
| Supervisor "Limited" is undefined in FDS | Implemented as read-only; **confirm with Tech Lead / client** |
| Account enumeration | Identical responses for unknown/known email and bad credentials |
| Brute-force login | Rate limiting added (login 10/min, reset 5/hour per client; configurable via env). Account lockout not implemented - not in FDS |
| Reset link host | `FRONTEND_RESET_URL` must be set per environment |
| Session cookies over HTTP | `Secure` flag on when DEBUG is off; HTTPS required in production |
| Admin lockout | Admin cannot deactivate or demote self |
