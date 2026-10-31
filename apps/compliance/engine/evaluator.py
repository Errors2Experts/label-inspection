"""Rules engine (FDS 12.3): verified label data + a list of rule specs -> rule-by-rule outcomes -> overall result.

Pure Python (no Django imports) so it can be unit-tested without a database. The service layer
(`apps.compliance.services`) loads RuleVersions from the database and feeds them in as `RuleSpec`s.

Rules are *data*, not code: each spec has a `rule_type` plus JSON `parameters`, so admins can add or change
rules without a deploy (FDS 12.3 "configurable rather than hard-coded"). Supported types are in `RULE_TYPES`.

Outcomes (FDS 12.3 / FR-COMP-004): compliant | non_compliant | requires_verification | not_applicable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from .dates import parse_label_date

COMPLIANT = 'compliant'
NON_COMPLIANT = 'non_compliant'
REQUIRES_VERIFICATION = 'requires_verification'
NOT_APPLICABLE = 'not_applicable'
OUTCOMES = (COMPLIANT, NON_COMPLIANT, REQUIRES_VERIFICATION, NOT_APPLICABLE)

# Fields of VerifiedInspectionData (FDS 11.4) that rules may read.
DATA_FIELDS = {
    'product_name': 'Name of food',
    'brand': 'Brand',
    'mrp': 'MRP',
    'net_quantity': 'Net quantity',
    'manufacturing_date': 'Date of manufacture / packing',
    'best_before': 'Best before date',
    'expiry_date': 'Expiry / use-by date',
    'ingredients': 'List of ingredients',
    'fssai_license': 'FSSAI licence number',
    'manufacturer': 'Manufacturer details',
    'packer': 'Packer details',
    'importer': 'Importer details',
    'other_declarations': 'Other declarations',
}

MAX_TEXT = 5000  # cap on text a rule examines (guards against pathological regex input)
MAX_PATTERN = 300

# Net quantity as printed: "500 g", "1.5 L", "2 x 100 g", "250ml", "6 Nos"
QUANTITY_RE = re.compile(
    r'^\s*(?:\d+\s*[x×]\s*)?\d+(?:[.,]\d+)?\s*(?:mg|g|gm|gms|gram|grams|kg|kgs|ml|l|ltr|litre|litres|liter|liters|cl'
    r'|nos?|pcs?|pieces?|units?|tablets?|capsules?)\b',
    re.I,
)


@dataclass(frozen=True)
class RuleSpec:
    """One rule version, flattened for evaluation."""

    code: str
    title: str
    rule_type: str
    parameters: dict = field(default_factory=dict)
    applies_when: list = field(default_factory=list)
    on_fail: str = NON_COMPLIANT  # outcome when the check fails (use requires_verification for heuristic rules)
    failure_message: str = ''


@dataclass(frozen=True)
class RuleOutcome:
    code: str
    outcome: str
    detail: str
    observed: str = ''


# ----------------------------------------------------------------------------- helpers
def label(field_name: str) -> str:
    return DATA_FIELDS.get(field_name, field_name)


def _fields(params: dict) -> list[str]:
    raw = params.get('fields') or params.get('field') or []
    return [raw] if isinstance(raw, str) else list(raw)


def _text(data: dict, name: str) -> str:
    value = data.get(name)
    if value is None:
        return ''
    return str(value).strip()[:MAX_TEXT]


def _joined(data: dict, names: list[str]) -> str:
    return '\n'.join(t for t in (_text(data, n) for n in names) if t)


def _fail(spec: RuleSpec, detail: str, observed: str = '') -> RuleOutcome:
    return RuleOutcome(spec.code, spec.on_fail, detail, observed[:500])


def _ok(spec: RuleSpec, detail: str, observed: str = '') -> RuleOutcome:
    return RuleOutcome(spec.code, COMPLIANT, detail, observed[:500])


def _missing(spec: RuleSpec, params: dict, detail: str) -> RuleOutcome:
    """Outcome when the field a check needs is empty. `on_missing` param: not_applicable (default) | fail | requires_verification."""
    mode = params.get('on_missing', 'not_applicable')
    if mode == 'fail':
        return _fail(spec, detail)
    if mode == 'requires_verification':
        return RuleOutcome(spec.code, REQUIRES_VERIFICATION, detail)
    return RuleOutcome(spec.code, NOT_APPLICABLE, detail)


# ----------------------------------------------------------------------------- applicability
CONDITION_OPS = ('present', 'absent', 'contains_any', 'not_contains_any')


def _contains_any(text: str, values: list[str]) -> bool:
    low = text.lower()
    return any(str(v).lower() in low for v in values if str(v).strip())


def conditions_met(conditions: list[dict], data: dict) -> bool:
    """All `applies_when` conditions must hold, otherwise the rule is Not Applicable.

    Condition: {"field": "importer", "op": "present"} or {"field": "ingredients", "op": "contains_any", "values": [..]}
    `field` may be a list; the texts are joined.
    """
    for cond in conditions or []:
        names = _fields(cond)
        text = _joined(data, names)
        op = cond.get('op')
        if op == 'present' and not text:
            return False
        if op == 'absent' and text:
            return False
        if op == 'contains_any' and not _contains_any(text, cond.get('values', [])):
            return False
        if op == 'not_contains_any' and _contains_any(text, cond.get('values', [])):
            return False
    return True


# ----------------------------------------------------------------------------- rule types
def _required(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    names = _fields(p)
    present = [n for n in names if _text(data, n)]
    if p.get('mode', 'all') == 'any':
        if present:
            return _ok(spec, f'Declared: {", ".join(label(n) for n in present)}.')
        return _fail(spec, f'None of the required particulars found: {", ".join(label(n) for n in names)}.')
    absent = [n for n in names if n not in present]
    if not absent:
        return _ok(spec, 'All required particulars are declared.')
    return _fail(spec, f'Not declared: {", ".join(label(n) for n in absent)}.')


def _regex(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    text = _joined(data, _fields(p))
    if not text:
        return _missing(spec, p, 'Nothing to check: the field is empty.')
    flags = re.I if p.get('ignore_case', True) else 0
    found = re.search(p['pattern'], text, flags) is not None
    expect = p.get('expect', 'match')  # match | no_match
    if found == (expect == 'match'):
        return _ok(spec, 'Pattern check passed.', text)
    return _fail(spec, p.get('fail_detail') or ('Value does not match the required format.' if expect == 'match' else 'Prohibited text found.'), text)  # noqa: E501


def _quantity_format(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    text = _joined(data, _fields(p) or ['net_quantity'])
    if not text:
        return _missing(spec, p, 'Net quantity is empty.')
    if QUANTITY_RE.search(text):
        return _ok(spec, 'Net quantity is a value with a unit.', text)
    return _fail(spec, 'Net quantity should be a number with a unit, e.g. "500 g" or "1 L".', text)


def _date_valid(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    names = _fields(p)
    filled = [n for n in names if _text(data, n)]
    if not filled:
        return _missing(spec, p, 'No dates to check.')
    bad = [n for n in filled if parse_label_date(_text(data, n)) is None]
    if bad:
        return _fail(spec, f'Not a recognised date format (DD/MM/YY, DD/MM/YYYY or MMM/YYYY): {", ".join(label(n) for n in bad)}.', '; '.join(_text(data, n) for n in bad))  # noqa: E501
    return _ok(spec, 'Date format is valid.')


def _date_order(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    first, second = p['first_field'], p['second_field']
    t1, t2 = _text(data, first), _text(data, second)
    if not t1 or not t2:
        return _missing(spec, p, 'Both dates are needed to compare them.')
    d1, d2 = parse_label_date(t1), parse_label_date(t2)
    if d1 is None or d2 is None:
        return RuleOutcome(spec.code, REQUIRES_VERIFICATION, 'A date could not be read; compare the dates manually.', f'{t1} / {t2}')  # noqa: E501
    if d2.end >= d1.start:
        return _ok(spec, f'{label(second)} is not before {label(first)}.', f'{t1} / {t2}')
    return _fail(spec, f'{label(second)} ({t2}) is earlier than {label(first)} ({t1}).', f'{t1} / {t2}')


def _not_expired(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    name = p.get('field', 'expiry_date')
    text = _text(data, name)
    if not text:
        return _missing(spec, p, 'No expiry date to check.')
    parsed = parse_label_date(text)
    if parsed is None:
        return RuleOutcome(spec.code, REQUIRES_VERIFICATION, 'Expiry date could not be read; check it manually.', text)
    today = ctx.get('reference_date') or date.today()
    if parsed.end >= today:
        return _ok(spec, f'Not expired on {today:%d %b %Y}.', text)
    return _fail(spec, f'Expired: {text} is before {today:%d %b %Y}.', text)


def _contains_any_rule(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    text = _joined(data, _fields(p))
    keywords = p.get('keywords', [])
    if text and _contains_any(text, keywords):
        return _ok(spec, 'Expected declaration found.', text)
    return _fail(spec, p.get('fail_detail') or f'Expected one of: {", ".join(map(str, keywords))}. Verify against the pack.', text)  # noqa: E501


def _numeric_min(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    p = spec.parameters
    name = (_fields(p) or ['mrp'])[0]
    raw = data.get(name)
    if raw is None or str(raw).strip() == '':
        return _missing(spec, p, f'{label(name)} is empty.')
    try:
        value = Decimal(str(raw).replace(',', '').replace('₹', '').strip())
    except InvalidOperation:
        return RuleOutcome(spec.code, REQUIRES_VERIFICATION, f'{label(name)} is not a number.', str(raw))
    minimum = Decimal(str(p.get('min', 0)))
    good = value > minimum if p.get('exclusive', True) else value >= minimum
    if good:
        return _ok(spec, f'{label(name)} is {value}.', str(value))
    return _fail(spec, f'{label(name)} must be greater than {minimum}.' if p.get('exclusive', True) else f'{label(name)} must be at least {minimum}.', str(value))  # noqa: E501


def _manual_check(spec: RuleSpec, data: dict, ctx: dict) -> RuleOutcome:
    """Cannot be decided from the extracted fields (needs the physical label); always asks the inspector to verify."""
    return RuleOutcome(spec.code, REQUIRES_VERIFICATION, spec.parameters.get('prompt') or 'Verify on the physical label.')


RULE_TYPES = {
    'required': _required,
    'regex': _regex,
    'quantity_format': _quantity_format,
    'date_valid': _date_valid,
    'date_order': _date_order,
    'not_expired': _not_expired,
    'contains_any': _contains_any_rule,
    'numeric_min': _numeric_min,
    'manual_check': _manual_check,
}


# ----------------------------------------------------------------------------- validation (FDS 12.7)
def validate_rule_config(rule_type: str, parameters: dict, applies_when: list, on_fail: str) -> list[str]:
    """Return a list of human-readable problems; empty list = valid. Called before a rule version is saved."""
    errors: list[str] = []
    if rule_type not in RULE_TYPES:
        return [f'Unknown rule type "{rule_type}". Choose one of: {", ".join(RULE_TYPES)}.']
    if not isinstance(parameters, dict):
        return ['Parameters must be a JSON object.']
    if on_fail not in (NON_COMPLIANT, REQUIRES_VERIFICATION):
        errors.append('on_fail must be "non_compliant" or "requires_verification".')

    def check_fields(names, key='fields'):
        if not names:
            errors.append(f'"{key}" must name at least one field.')
        for n in names:
            if n not in DATA_FIELDS:
                errors.append(f'Unknown data field "{n}". Valid fields: {", ".join(DATA_FIELDS)}.')

    if rule_type in ('required', 'date_valid', 'regex', 'contains_any'):
        check_fields(_fields(parameters))
    if rule_type == 'required' and parameters.get('mode', 'all') not in ('all', 'any'):
        errors.append('"mode" must be "all" or "any".')
    if rule_type == 'regex':
        pattern = parameters.get('pattern')
        if not isinstance(pattern, str) or not pattern:
            errors.append('"pattern" is required.')
        elif len(pattern) > MAX_PATTERN:
            errors.append(f'"pattern" is longer than {MAX_PATTERN} characters.')
        else:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f'"pattern" is not a valid regular expression: {exc}.')
        if parameters.get('expect', 'match') not in ('match', 'no_match'):
            errors.append('"expect" must be "match" or "no_match".')
    if rule_type == 'contains_any':
        kw = parameters.get('keywords')
        if not isinstance(kw, list) or not [k for k in kw if str(k).strip()]:
            errors.append('"keywords" must be a non-empty list of words or phrases.')
    if rule_type == 'date_order':
        for key in ('first_field', 'second_field'):
            if parameters.get(key) not in DATA_FIELDS:
                errors.append(f'"{key}" must be one of: {", ".join(DATA_FIELDS)}.')
    if rule_type in ('not_expired', 'numeric_min', 'quantity_format'):
        names = _fields(parameters)
        for n in names:
            if n not in DATA_FIELDS:
                errors.append(f'Unknown data field "{n}".')
    if rule_type == 'numeric_min':
        try:
            Decimal(str(parameters.get('min', 0)))
        except InvalidOperation:
            errors.append('"min" must be a number.')
    if parameters.get('on_missing', 'not_applicable') not in ('not_applicable', 'fail', 'requires_verification'):
        errors.append('"on_missing" must be "not_applicable", "fail" or "requires_verification".')

    if not isinstance(applies_when, list):
        errors.append('applies_when must be a list of conditions.')
    else:
        for i, cond in enumerate(applies_when, 1):
            if not isinstance(cond, dict) or cond.get('op') not in CONDITION_OPS:
                errors.append(f'Condition {i}: "op" must be one of {", ".join(CONDITION_OPS)}.')
                continue
            for n in _fields(cond):
                if n not in DATA_FIELDS:
                    errors.append(f'Condition {i}: unknown data field "{n}".')
            if not _fields(cond):
                errors.append(f'Condition {i}: "field" is required.')
            if cond['op'] in ('contains_any', 'not_contains_any') and not cond.get('values'):
                errors.append(f'Condition {i}: "values" must be a non-empty list.')
    return errors


# ----------------------------------------------------------------------------- evaluation
def evaluate_rule(spec: RuleSpec, data: dict, ctx: dict | None = None) -> RuleOutcome:
    """Evaluate one rule. Never raises: a broken rule yields Requires Verification so one bad rule cannot sink a run."""
    ctx = ctx or {}
    if not conditions_met(spec.applies_when, data):
        return RuleOutcome(spec.code, NOT_APPLICABLE, 'Rule does not apply to this product.')
    handler = RULE_TYPES.get(spec.rule_type)
    if handler is None:
        return RuleOutcome(spec.code, REQUIRES_VERIFICATION, f'Unknown rule type "{spec.rule_type}"; verify manually.')
    try:
        return handler(spec, data, ctx)
    except Exception as exc:  # noqa: BLE001 - isolate misconfigured rules
        return RuleOutcome(spec.code, REQUIRES_VERIFICATION, f'Rule could not be evaluated ({type(exc).__name__}); verify manually.')  # noqa: E501


def overall_status(outcomes: list[str]) -> str:
    """Aggregate per-rule outcomes: any failure -> non_compliant; else any open check -> requires_verification;
    else compliant; if nothing applied -> not_applicable."""
    if NON_COMPLIANT in outcomes:
        return NON_COMPLIANT
    if REQUIRES_VERIFICATION in outcomes:
        return REQUIRES_VERIFICATION
    if COMPLIANT in outcomes:
        return COMPLIANT
    return NOT_APPLICABLE


def evaluate_rules(specs: list[RuleSpec], data: dict, ctx: dict | None = None) -> tuple[str, list[RuleOutcome]]:
    outcomes = [evaluate_rule(spec, data, ctx) for spec in specs]
    return overall_status([o.outcome for o in outcomes]), outcomes
