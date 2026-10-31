# Code Flow - Module 4: Compliance Rules

## 1. Edit a rule (versioning)
Edit Rule form -> `compliance.js initRuleForm` -> `PUT /api/rules/{id}/` -> `RuleSerializer.validate` (`engine.validate_rule_config`) ->
`RuleSerializer.update` saves rule metadata -> if logic changed, `services.add_version` marks the old version `is_current=False` and inserts version n+1 -> response -> redirect to `/rules/`.
Packs keep their old pin until "Update to latest versions" (`POST /api/rule-packs/{id}/refresh/` -> `services.refresh_pack`).

## 2. Evaluate
`POST /api/compliance/evaluate/` {data, pack?, category?, reference?, reference_date?}
-> `EvaluateRequestSerializer` (known fields only, at least one value)
-> pack = given pack (draft refused) or `services.select_pack(category, date)` (active, in date window, category match; category-specific beats general; newest effective date)
-> `services.evaluate`: load the pack's items plus those of the pack it `extends` (`services.effective_items`; a Dairy evaluation also runs the Basic pack's rules), keep active rules -> `RuleSpec` list -> `engine.evaluator.evaluate_rules`
   - per rule: `conditions_met(applies_when)` -> else Not Applicable; then the handler for `rule_type`; any exception -> Requires Verification
   - overall: any Non-Compliant -> Non-Compliant; else any Requires Verification -> Requires Verification; else Compliant; nothing applied -> Not Applicable
-> one transaction stores `ComplianceResult` (snapshot of data, pack name/version), a `RuleEvaluation` per rule (snapshot of code, title, severity, version number) and a `Violation` per Non-Compliant rule
-> 201 with the full result -> UI redirects to `/rules/results/{id}/`.

## 3. Engine
`engine/evaluator.py` and `engine/dates.py` are pure Python (no Django) and unit-tested without a database. Rule types: `required`, `regex`, `quantity_format`, `date_valid`, `date_order`, `not_expired`, `contains_any`, `numeric_min`, `manual_check`. Add a type by writing a handler, registering it in `RULE_TYPES`, and adding validation in `validate_rule_config`.

## 4. Seed
`python manage.py seed_compliance` -> `fssai_rules.py` data -> categories, rules (version 1), the three packs (Basic v2.1, Dairy v1.3, Import v1.0 draft) with pinned versions; Dairy and Import extend Basic. Safe to re-run; never overwrites admin edits.


## Add / Edit Rule form (guided)

`rule_form.html` + `compliance.js initRuleForm`. FDS 12.3 asks for configurable rules and 12.7 for validated parameters. The form keeps both and hides the JSON:

1. **Check type** is a plain-language dropdown. Choosing one draws its own controls: field tick-boxes, a comma-separated word list, date and number selects, or an inspector prompt (`renderGuided`).
2. **When does this rule apply?** is "To every product" or a builder of conditions (field + is filled in / is empty / contains any of / does not contain any of), saved as `applies_when`.
3. On Save, `readGuided` / `readConditions` build the same `parameters` and `applies_when` the engine already uses. Defaults (`mode: all`, `expect: match`, `exclusive: true`) are left out, so saving an unchanged rule does not create a new version. Settings the form has no control for (for example `fail_detail`) are kept as saved.
4. **Advanced** shows the two JSON boxes for experts; switching back re-draws the guided form from the JSON.
5. The server still validates everything (`engine.validate_rule_config`); its messages appear in the form banner.
