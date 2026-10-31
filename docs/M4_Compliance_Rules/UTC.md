# UTC - Module 4: Compliance Rules

| Item | Detail |
|---|---|
| Developer | Mr. Sathish Vishnu A |
| Window | 16/10/2026 - 25/10/2026 |
| FDS reference | Section 12 (FR-COMP-001 to FR-COMP-004) |
| Automated tests | `apps/compliance/tests/` - 47 tests; run `python manage.py test apps.compliance` |
| Test database | SQLite (no external calls) |
| Status | Draft - automated tests passing; manual browser walk-through pending |

## 1. Use cases
| ID | Use case | Actor | Main flow |
|---|---|---|---|
| UC-M4-01 | Browse rules and packs | Admin, Supervisor | Open Compliance Rules -> see counts, the three packs and the rules of the pack chosen with View |
| UC-M4-02 | Add or edit a rule | Admin, Supervisor | Fill form (check type + JSON parameters) -> validated -> saved; changed logic appends a new version |
| UC-M4-03 | Review rule versions | Admin, Supervisor | Rule -> Versions -> full history with notes |
| UC-M4-04 | Manage categories | Admin, Supervisor | Add / rename / delete (blocked while rules use it) |
| UC-M4-05 | Build a rule pack | Admin, Supervisor | Create pack (optionally "Also apply rules of" a base pack) -> add rules (pinned versions) -> set status and effective dates -> "Update to latest versions" |
| UC-M4-06 | Evaluate verified label data | All roles (API); Admin/Supervisor (test screen) | Verified data + pack -> rule-by-rule outcomes -> overall result + stored violations |
| UC-M4-07 | Review results and violations | All roles (inspectors: own only) | Results list -> result detail; Violations list with filters |

## 2. Test cases
| Test ID | Area | Steps / input | Expected result | Status |
|---|---|---|---|---|
| M4-TC-001 | Date parsing | DD/MM/YY, DD/MM/YYYY, DD-MON-YY, MON YYYY, MM/YYYY | parsed with right precision | Pass |
| M4-TC-002 | Date parsing | 'EXP: 01/03/2027', 'Best before 03/2027', junk, impossible dates | prefix stripped; junk -> None | Pass |
| M4-TC-003 | required | all / any mode | compliant when declared, non-compliant naming the gap | Pass |
| M4-TC-004 | on_fail | heuristic rule set to requires_verification | failure becomes Requires Verification | Pass |
| M4-TC-005 | regex | licence 14 digits; empty field with each on_missing mode | match / fail / n.a. / verify | Pass |
| M4-TC-006 | quantity_format | '500 g', '1.5 L', '2 x 100 g' ok; 'big pack', '500' not | pass/fail | Pass |
| M4-TC-007 | date_valid / date_order | bad format, expiry before mfg, unreadable | non-compliant / verify | Pass |
| M4-TC-008 | not_expired | past, today, month-precision end, future, unreadable | verdicts against reference date | Pass |
| M4-TC-009 | contains_any / numeric_min / manual_check | keyword hit & miss, MRP bounds, manual prompt | outcomes | Pass |
| M4-TC-010 | applies_when | present/absent/contains_any/not_contains_any | Not Applicable when conditions fail | Pass |
| M4-TC-011 | Robustness | unknown type, missing parameter | Requires Verification, no exception | Pass |
| M4-TC-012 | Aggregation | mixes of outcomes | non-compliant > requires verification > compliant > n.a. | Pass |
| M4-TC-013 | Validation (FDS 12.7) | bad type/field/regex/op/on_fail | readable errors; valid config -> [] | Pass |
| M4-TC-020 | Seed | run seed_compliance twice | 26 rules, 6 categories, 3 packs (12 / 8 / 6 rules), no duplicates | Pass |
| M4-TC-021 | Content | seeded rules | first two match the design; vegan 2022 rules present; nothing from the 2026 amendment | Pass |
| M4-TC-030 | RBAC | Anonymous, Inspector, Supervisor, Admin call /api/rules/ | 403, 403, 200, 200 | Pass |
| M4-TC-031 | RBAC | Inspector POSTs rule / pack / category | 403 each | Pass |
| M4-TC-040 | Create rule | POST without code | R-027 assigned, version 1 created and current | Pass |
| M4-TC-041 | Validation | bad type, bad field, bad regex, duplicate code, missing name | 400 with field errors | Pass |
| M4-TC-042 | Versioning | PUT changed parameters | version 2 current, version 1 untouched and still stored | Pass |
| M4-TC-043 | Versioning | PATCH title/severity/is_active only | no new version | Pass |
| M4-TC-044 | List | ?q ?category ?severity ?active ?pack | each narrows the list | Pass |
| M4-TC-045 | Delete | unused rule vs rule in a pack | 204 vs 409 and rule kept | Pass |
| M4-TC-046 | Support endpoints | /meta/ and /summary/ | choices present; counts 26 / 3 / 6 | Pass |
| M4-TC-050 | Categories | create, duplicate name, rename, delete used / unused | 201, 400, 200, 409, 204 | Pass |
| M4-TC-060 | Packs | list | design order: Basic v2.1 (12, active), Dairy v1.3 (8, active), Import v1.0 (6, draft) | Pass |
| M4-TC-061 | Packs | create empty pack, add rule, re-pin to older version, remove, refresh | items & versions correct | Pass |
| M4-TC-062 | Packs | duplicate name, end before start | 400 | Pass |
| M4-TC-063 | Packs | delete a pack that has results vs one that has none | 409 vs 204 | Pass |
| M4-TC-064 | Packs | extends: self, chained, and a valid base | 400, 400, 200; pack serialises extends | Pass |
| M4-TC-070 | Pack selection | Dairy / other category / before 2022 / draft pack | Dairy pack, Basic, none, never the draft | Pass |
| M4-TC-080 | Evaluate | complete, valid label (default pack) | 201, 0 violations, overall Requires Verification (physical-label checks) | Pass |
| M4-TC-081 | Evaluate | missing licence, bad quantity, expiry in the past, no MRP | non-compliant; one Violation per failed rule | Pass |
| M4-TC-082 | Evaluate | category Dairy | Dairy pack chosen; 20 rules (8 own + 12 from Basic); sweetener rule fails then passes | Pass |
| M4-TC-083 | Evaluate | vegan claim; Import pack (draft: via service) | R-012 asks to verify; importer / licence / origin rules fire | Pass |
| M4-TC-084 | Versioning | evaluate, then edit the rule | stored evaluation still points to the old version and old wording | Pass |
| M4-TC-085 | Evaluate | empty data, unknown field, draft pack, no pack applies, pack with no rules | 400 each | Pass |
| M4-TC-086 | Evaluate | deactivate R-001 | rule not evaluated | Pass |
| M4-TC-087 | Evaluate | anonymous | 403 | Pass |
| M4-TC-090 | Results & violations | two inspectors + supervisor list | inspector: own only; supervisor: all; other's detail 404 | Pass |
| M4-TC-091 | Results | evaluate without reference_date | stored reference_date is today | Pass |
| M4-TC-100 | Page access | anonymous GET of every compliance page | 302 to /login/?next= | Pass |
| M4-TC-101 | Role access | management pages as Admin/Supervisor vs Inspector | 200 vs 403 | Pass |
| M4-TC-102 | Role access | results list, violations, result detail | 200 for every role | Pass |
| M4-TC-103 | Navigation | Compliance Rules link | present and live for staff, absent for inspector | Pass |
| M4-TC-104 | Design | Compliance Rules overview | 3 stat cards, Rule Packs table with View, Rules table (ID, name, category, severity, status) | Pass |
| M4-TC-105 | Usability | Add Rule page | plain-language check types, field tick-boxes and condition builder; JSON only behind Advanced | Pass |

## 3. Manual checks still to do
- Walk through every screen in Chrome and Edge on desktop and a tablet width.
- Compare the Compliance Rules overview and Product Catalogue screens against the approved screenshots (checked once with a headless browser on 29 Oct 2026).
- Have a domain reviewer confirm the seeded FSSAI rules (see `Rule_Catalogue.md`) against the Gazette text. The 2026 amendment (effective 1 July 2027) is intentionally not seeded. The 2026 amendment (effective 1 July 2027) is intentionally not seeded.
- Guided rule form (M4-UI-20): Add Rule: pick each check type -> Matching controls appear (tick-boxes, words, dates, number, prompt); no JSON visible
- Guided rule form (M4-UI-21): Add Rule: leave nothing ticked, press Save -> Plain message such as "Tick at least one field that must be filled in."
- Guided rule form (M4-UI-22): Add Rule: "Only when" builder with a condition -> Saved rule shows the condition; evaluation applies it
- Guided rule form (M4-UI-23): Edit any seeded rule and Save without changes -> No new version is created
- Guided rule form (M4-UI-24): Tick Advanced -> JSON boxes show the same settings; unticking redraws the simple form
