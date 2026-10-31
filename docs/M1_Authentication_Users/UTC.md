# UTC - Module 1: Authentication and Users

| Item | Detail |
|---|---|
| Developer | Manishashri P |
| Window | 05/10/2026 - 15/10/2026 |
| FDS reference | Section 9, FR-AUTH-001 to FR-AUTH-005 |
| Automated tests | `apps/accounts/tests/` (52 tests; run `python manage.py test apps.accounts`) |
| Status | Draft - automated tests passing; manual UI testing pending |

## 1. Use cases

| ID | Use case | Actor | Main flow |
|---|---|---|---|
| UC-M1-01 | Log in | All roles | Enter username/email + password -> credential check -> role resolved -> session created -> redirect to authorised area |
| UC-M1-02 | Log out | All roles | Logout -> session destroyed |
| UC-M1-03 | Reset forgotten password | All roles | Enter email -> receive link -> set new password -> log in |
| UC-M1-04 | Manage inspector accounts | Admin | Create / view / edit / deactivate / reactivate users, assign role |
| UC-M1-05 | View users | Supervisor | Read-only list and details (FDS "Limited") |
| UC-M1-06 | Manage own profile | All roles | View/update profile, change password |
| UC-M1-07 | View roles and permissions | Admin, Supervisor | Read role-permission matrix |

## 2. Test cases

| Test ID | Area | Scenario | Input / steps | Expected result | Status |
|---|---|---|---|---|---|
| M1-TC-001 | Login | Login with valid username | POST /api/auth/login/ {identifier: insp1, password: valid} | 200; session cookie set; user + role returned | Pass |
| M1-TC-002 | Login | Login with email (any letter case) | identifier = INSP1@lip.test, valid password | 200; logged in | Pass |
| M1-TC-003 | Login | Wrong password | valid username, wrong password | 401 'Invalid username/email or password.' | Pass |
| M1-TC-004 | Login | No account-existence leak | wrong password vs non-existent username | Identical status and message in both cases | Pass |
| M1-TC-005 | Login | Deactivated account | is_active=False, correct password | 401; cannot log in | Pass |
| M1-TC-006 | Login | Mandatory fields | Omit password | 400 with field error | Pass |
| M1-TC-007 | Logout | Logout ends session | Login, GET profile, POST /api/auth/logout/, GET profile | Profile 200 before; 401/403 after | Pass |
| M1-TC-008 | Security | Protected endpoint without login | GET /api/users/ unauthenticated | 401/403 | Pass |
| M1-TC-009 | Security | CSRF enforced on login | POST login without CSRF token | 403 | Pass |
| M1-TC-010 | Security | Login rate limit | 11 failed logins within a minute | First 10 return 401; 11th returns 429 | Pass |
| M1-TC-011 | Security | Password-reset rate limit | 6 reset requests within an hour | 6th returns 429 | Pass |
| M1-TC-020 | Password reset | Reset email for known user | POST /api/auth/password-reset/ {email} | 200 generic message; 1 email with uid+token link | Pass |
| M1-TC-021 | Password reset | Unknown email | Request reset for unregistered email | Same 200 response as known email; no email sent | Pass |
| M1-TC-022 | Password reset | End-to-end reset | Request, take uid/token from email, POST confirm with strong password, then login | 200; login works with the new password | Pass |
| M1-TC-023 | Password reset | Token single-use | Reuse the same token | 2nd confirm returns 400 | Pass |
| M1-TC-024 | Password reset | Invalid token | Confirm with a bad token | 400 generic 'invalid or expired' message | Pass |
| M1-TC-025 | Password reset | Password policy on reset | new_password = 12345678 | 400 with password errors | Pass |
| M1-TC-026 | Password reset | Inactive user | Request reset for deactivated user | 200 generic; no email sent | Pass |
| M1-TC-030 | User mgmt | Admin creates inspector | Admin POST /api/users/ valid payload | 201; password hashed; password not in response | Pass |
| M1-TC-031 | User mgmt | Unique username | Create with existing username | 400 | Pass |
| M1-TC-031b | User mgmt | Username unique ignoring case | Create 'INSP1' when 'insp1' exists | 400 on username | Pass |
| M1-TC-032 | User mgmt | Unique email (case-insensitive) | Create with INSP1@lip.test | 400 on email | Pass |
| M1-TC-033 | User mgmt | Mandatory fields | POST {username only} | 400; email and password errors | Pass |
| M1-TC-034 | User mgmt | Password strength | Passwords: short1, 12345678, password | 400 for each | Pass |
| M1-TC-035 | User mgmt | Admin edits user / role | PUT /api/users/{id}/ with changed name, role | 200; values saved | Pass |
| M1-TC-036 | User mgmt | Deactivate (soft delete) | DELETE /api/users/{id}/ | 200; is_active=False; row still exists | Pass |
| M1-TC-037 | User mgmt | Deactivate then reactivate | Deactivate, try login, POST activate, login | 401 while inactive; 200 after activation | Pass |
| M1-TC-038 | User mgmt | Admin self-protection | Admin deletes self / changes own role | 400 for both | Pass |
| M1-TC-039 | User mgmt | List filters and search | ?role=, ?q=, ?is_active= | Only matching users returned | Pass |
| M1-TC-040 | RBAC | Inspector denied | Inspector calls users list/create, roles | 403 | Pass |
| M1-TC-041 | RBAC | Supervisor limited | Supervisor: GET users; POST/DELETE/PATCH users | GET 200; write calls 403 | Pass |
| M1-TC-042 | RBAC | Roles & permissions screen | Admin GET /api/roles/ | 3 roles + FDS 7.2 matrix | Pass |
| M1-TC-043 | RBAC | Superuser role | createsuperuser | role forced to admin | Pass |
| M1-TC-044 | RBAC | Reusable permission classes | IsAdmin / IsAdminOrSupervisor / IsAnyRole per role | Matches FDS 7.2 for each role | Pass |
| M1-TC-050 | Profile | View own profile | GET /api/profile/ | 200; own data | Pass |
| M1-TC-051 | Profile | Update own profile | PUT /api/profile/ name, email, phone | 200; saved | Pass |
| M1-TC-052 | Profile | No privilege escalation | PATCH role=admin, username, employee_id | Ignored; role/username unchanged | Pass |
| M1-TC-053 | Profile | Unique email | PATCH email of another user | 400 | Pass |
| M1-TC-054 | Profile | Change password | POST change-password with correct old password | 200; new password works; session stays valid | Pass |
| M1-TC-055 | Profile | Wrong current password | old_password wrong | 400 | Pass |
| M1-TC-056 | Profile | Weak new password | new_password = 12345678 | 400 | Pass |
| M1-TC-057 | Profile | Login required | GET profile unauthenticated | 401/403 | Pass |
| M1-TC-060 | Pages | Login page public, sets CSRF cookie | GET /login/ | 200; csrftoken cookie | Pass |
| M1-TC-061 | Pages | Protected pages redirect | Anonymous GET dashboard/users/roles/profile | 302 to /login/?next= | Pass |
| M1-TC-062 | Pages | Logged-in user skips login | GET /login/ when authenticated | Redirect to dashboard | Pass |
| M1-TC-063 | Pages | Inspector blocked from admin pages | Inspector GET users/roles/add/detail | 403 | Pass |
| M1-TC-064 | Pages | Supervisor read-only pages | Supervisor GET users, roles, add, edit | 200, 200, 403, 403; no Add button | Pass |
| M1-TC-065 | Pages | Admin opens every M1 page | Admin GET all pages | 200 | Pass |
| M1-TC-066 | Pages | Sidebar filtered by role | Inspector vs Admin dashboard HTML | Inspector lacks Compliance Rules / Roles; Admin has both | Pass |
| M1-TC-067 | Pages | Home redirect | GET / | Redirect to dashboard | Pass |
| M1-TC-068 | Pages | Static assets resolvable | CSS/JS files found by staticfiles | All found | Pass |
| M1-TC-069 | Pages | Display name and initials | first+last name / username fallback | 'SV' / 'SU'; also in /api/profile/ | Pass |

## 3. Acceptance criteria traceability (FDS 9.9)

| Acceptance criterion | Covered by |
|---|---|
| Valid login works, invalid denied | M1-TC-001 to 011 |
| Roles restrict access to unauthorised functions | M1-TC-040 to 044, 008 |
| Admin can create, edit, deactivate inspector accounts | M1-TC-030 to 039 |
| Password reset works end-to-end | M1-TC-020 to 026 |

## 4. Pending manual tests
- Browser UI checklist M1-UI-01 to M1-UI-12 in `Frontend.md` (screens now built; not yet run in a browser)
- Cross-browser cookie behaviour over HTTPS
- Real SMTP delivery of reset email
