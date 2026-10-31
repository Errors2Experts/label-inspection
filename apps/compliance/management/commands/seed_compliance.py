from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.compliance import services
from apps.compliance.engine.evaluator import validate_rule_config
from apps.compliance.fssai_rules import CATEGORIES, PACKS, RULES
from apps.compliance.models import ComplianceRule, RuleCategory, RulePack


class Command(BaseCommand):
    help = 'Load the FSSAI label categories, rules and the three rule packs (safe to re-run; never overwrites admin edits).'

    @transaction.atomic
    def handle(self, *args, **options):
        cats = {}
        for name, desc in CATEGORIES:
            cats[name], _ = RuleCategory.objects.get_or_create(name=name, defaults={'description': desc})

        rules = {}
        for code, title, cat, severity, ref, rtype, params, applies, on_fail, message in RULES:
            problems = validate_rule_config(rtype, params, applies, on_fail)
            if problems:  # a seed typo should fail loudly, not load a broken rule
                raise ValueError(f'{code}: {problems}')
            rule, _ = ComplianceRule.objects.get_or_create(
                code=code, defaults={'title': title, 'category': cats[cat], 'severity': severity, 'regulation_ref': ref}
            )
            if not rule.versions.exists():
                services.add_version(
                    rule,
                    {'rule_type': rtype, 'parameters': params, 'applies_when': applies, 'on_fail': on_fail, 'failure_message': message},
                    None,
                    'Seeded: FSSAI label rule (in force)',
                )
            rules[code] = rule

        created_packs = {}
        for spec in PACKS:
            spec = dict(spec)
            codes = spec.pop('rules')
            extends = spec.pop('extends')
            start = spec.pop('effective_from')
            spec['effective_from'] = date.fromisoformat(start) if start else None
            pack, _ = RulePack.objects.get_or_create(name=spec.pop('name'), defaults=spec)
            created_packs[pack.name] = pack
            if extends and pack.extends_id is None and extends in created_packs:
                pack.extends = created_packs[extends]
                pack.save(update_fields=['extends'])
            existing = set(pack.items.values_list('rule__code', flat=True))
            for code in codes:
                if code not in existing:
                    services.set_pack_rule(pack, rules[code])

        self.stdout.write(
            self.style.SUCCESS(
                f'Compliance rules ready: {ComplianceRule.objects.count()} rules, {RuleCategory.objects.count()} categories, '
                f'{RulePack.objects.count()} packs.'
            )
        )
        for pack in RulePack.objects.all():
            self.stdout.write(f'  {pack.name} {pack.version}: {pack.items.count()} rules ({pack.status})')
