# Impact Analysis - Module 4: Compliance Rules

| Area | Impact |
|---|---|
| New functionality | Rule categories, rules with immutable versions, rule packs (pinned versions, status, effective dates, optional "extends" base pack), rules engine, evaluation API, results and violations, 11 screens |
| Existing functionality changed | `apps/accounts/navigation.py` (Compliance Rules link now live, staff only); `config/urls.py` (page + API routes); `static/css/lip.css` (stat cards, tabs, result banner). Product Catalogue changed to the approved design: scanner screen removed, inline Manual Product Entry form with six fields, list in order added (see M2 docs) |
| Database | New tables: `compliance_rulecategory`, `compliancerule`, `ruleversion`, `rulepack`, `rulepackitem`, `complianceresult`, `ruleevaluation`, `violation` (migrations `compliance/0001_initial`, `0002_pack_extends` adds `RulePack.extends`). No change to other apps' tables |
| API | `/api/rules/` (+ `versions/`, `meta/`, `summary/`), `/api/rule-categories/`, `/api/rule-packs/` (+ `add-rule/`, `remove-rule/`, `refresh/`), `/api/compliance/evaluate/`, `/api/compliance/results/`, `/api/compliance/violations/` |
| UI | `/rules/`, `/rules/add/`, `/rules/<id>/edit/`, `/rules/<id>/versions/`, `/rules/categories/`, `/rules/packs/add/`, `/rules/packs/<id>/`, `/rules/evaluate/`, `/rules/results/`, `/rules/results/<id>/`, `/rules/violations/` |
| Integration | The Inspection module (not part of this delivery) should call `apps.compliance.services.evaluate(data, pack, user, reference)` or `POST /api/compliance/evaluate/` with inspector-verified data only. `ComplianceResult.reference` is a free text field until an Inspection foreign key is added |
| Security | Rule/pack/category management: Admin and Supervisor only (FDS 7.2). Evaluate / results: all roles; inspectors see only their own results and violations. Admin-supplied regex length-capped and validated; evaluated text capped at 5,000 characters |
| Dependencies | None beyond the project requirements (Django, DRF) |
| Risks | (1) Seeded FSSAI rules are written from the Labelling and Display compendium (Version VIII, Sep 2025), the Vegan Foods Regulations 2022 and import / dairy rules - a domain reviewer should confirm them. (2) The upcoming 2026 amendment is intentionally absent; add it when it takes effect. (3) Free-text fields limit what can be checked automatically; many checks return Requires Verification. (4) Rule parameters are edited as JSON; a guided editor would be friendlier |
