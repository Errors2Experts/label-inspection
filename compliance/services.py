"""Business logic for Module 4: rule versioning, pack selection and evaluation. Views stay thin."""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .engine import evaluator as ev
from .models import (
    ComplianceResult,
    ComplianceRule,
    Outcome,
    PackStatus,
    RuleEvaluation,
    RulePack,
    RulePackItem,
    RuleVersion,
    Violation,
)

CONFIG_KEYS = ('rule_type', 'parameters', 'applies_when', 'on_fail', 'failure_message')


class ComplianceError(Exception):
    """A business-rule problem that the API reports as 400/409."""


# ----------------------------------------------------------------------------- versions
@transaction.atomic
def add_version(rule: ComplianceRule, config: dict, user=None, note: str = '') -> RuleVersion:
    """Append a new current version; earlier versions stay untouched (FDS 12.7)."""
    last = rule.versions.aggregate(m=Max('version_number'))['m'] or 0
    rule.versions.filter(is_current=True).update(is_current=False)
    return RuleVersion.objects.create(
        rule=rule,
        version_number=last + 1,
        rule_type=config['rule_type'],
        parameters=config.get('parameters') or {},
        applies_when=config.get('applies_when') or [],
        on_fail=config.get('on_fail') or Outcome.NON_COMPLIANT,
        failure_message=config.get('failure_message', ''),
        change_note=note,
        created_by=user,
    )


def config_of(version: RuleVersion) -> dict:
    return {k: getattr(version, k) for k in CONFIG_KEYS}


def config_changed(version: RuleVersion | None, config: dict) -> bool:
    if version is None:
        return True
    return any(config.get(k, getattr(version, k)) != getattr(version, k) for k in CONFIG_KEYS)


# ----------------------------------------------------------------------------- packs
@transaction.atomic
def set_pack_rule(pack: RulePack, rule: ComplianceRule, version: RuleVersion | None = None) -> RulePackItem:
    """Put `rule` into `pack` pinned to `version` (default: the rule's current version); replaces an older pin."""
    version = version or rule.current_version
    if version is None or version.rule_id != rule.id:
        raise ComplianceError('That version does not belong to the rule.')
    item = pack.items.filter(rule=rule).first()
    if item:
        item.rule_version = version
        item.save(update_fields=['rule_version'])
        return item
    position = (pack.items.aggregate(m=Max('position'))['m'] or 0) + 1
    return RulePackItem.objects.create(pack=pack, rule=rule, rule_version=version, position=position)


@transaction.atomic
def refresh_pack(pack: RulePack) -> int:
    """Re-pin every item to its rule's current version. Returns how many items changed."""
    changed = 0
    for item in pack.items.select_related('rule_version', 'rule'):
        current = item.rule.current_version
        if current and current.id != item.rule_version_id:
            item.rule_version = current
            item.save(update_fields=['rule_version'])
            changed += 1
    return changed


def select_pack(category: str = '', on: date | None = None) -> RulePack | None:
    """Pick the pack to use when none is named: active on `on`, covering the product category.
    A pack with explicit categories beats a general one; ties go to the most recent effective date."""
    on = on or timezone.localdate()
    candidates = [p for p in RulePack.objects.filter(status=PackStatus.ACTIVE) if p.state_on(on) == 'active']
    candidates = [p for p in candidates if p.covers_category(category)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (bool(p.product_categories), p.effective_from or date.min, p.pk), reverse=True)
    return candidates[0]


def effective_items(pack: RulePack) -> list[RulePackItem]:
    """The pack's own rules plus those of the pack it extends (one level). A rule named in both keeps the pack's own pin."""
    items = list(pack.items.select_related('rule', 'rule__category', 'rule_version'))
    if pack.extends_id and pack.extends_id != pack.id:
        own = {i.rule_id for i in items}
        base = pack.extends.items.select_related('rule', 'rule__category', 'rule_version')
        items += [i for i in base if i.rule_id not in own]
    return items


# ----------------------------------------------------------------------------- evaluation
def clean_data(raw: dict) -> dict:
    """Keep only known label fields, as stripped text."""
    data = {}
    for key in ev.DATA_FIELDS:
        value = raw.get(key)
        data[key] = '' if value is None else str(value).strip()
    return data


@transaction.atomic
def evaluate(data: dict, pack: RulePack, user=None, reference: str = '', reference_date: date | None = None) -> ComplianceResult:
    """Evaluate verified label data against `pack` and store result, per-rule evaluations and violations.

    Callers must only pass *inspector-verified* data (FDS rule: AI has no final authority).
    """
    all_items = effective_items(pack)
    if not all_items:
        raise ComplianceError('This rule pack has no rules.')
    data = clean_data(data)
    reference_date = reference_date or timezone.localdate()
    items = sorted((i for i in all_items if i.rule.is_active), key=lambda i: i.rule.code)
    if not items:
        raise ComplianceError('This rule pack has no active rules.')
    specs = []
    for item in items:
        v = item.rule_version
        specs.append(
            ev.RuleSpec(
                code=item.rule.code,
                title=item.rule.title,
                rule_type=v.rule_type,
                parameters=v.parameters or {},
                applies_when=v.applies_when or [],
                on_fail=v.on_fail,
                failure_message=v.failure_message,
            )
        )
    overall, outcomes = ev.evaluate_rules(specs, data, {'reference_date': reference_date})
    counts = {o: 0 for o in ev.OUTCOMES}
    for o in outcomes:
        counts[o.outcome] += 1

    result = ComplianceResult.objects.create(
        pack=pack,
        pack_name=pack.name,
        pack_version=pack.version,
        reference=reference,
        reference_date=reference_date,
        data_snapshot=data,
        overall_status=overall,
        compliant_count=counts[ev.COMPLIANT],
        non_compliant_count=counts[ev.NON_COMPLIANT],
        verification_count=counts[ev.REQUIRES_VERIFICATION],
        not_applicable_count=counts[ev.NOT_APPLICABLE],
        evaluated_by=user,
    )
    for item, spec, out in zip(items, specs, outcomes, strict=True):
        rule, version = item.rule, item.rule_version
        evaluation = RuleEvaluation.objects.create(
            result=result,
            rule_version=version,
            rule_code=rule.code,
            rule_title=rule.title,
            category_name=rule.category.name,
            severity=rule.severity,
            regulation_ref=rule.regulation_ref,
            version_number=version.version_number,
            outcome=out.outcome,
            detail=out.detail[:500],
            observed=out.observed,
        )
        if out.outcome == ev.NON_COMPLIANT:
            Violation.objects.create(
                result=result,
                evaluation=evaluation,
                rule_version=version,
                rule_code=rule.code,
                rule_title=rule.title,
                category_name=rule.category.name,
                severity=rule.severity,
                regulation_ref=rule.regulation_ref,
                message=(spec.failure_message or out.detail)[:500],
            )
    return result
