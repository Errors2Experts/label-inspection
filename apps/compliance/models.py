"""Compliance Rules data model (FDS 12.5, 21.1).

    RuleCategory 1-* ComplianceRule 1-* RuleVersion
    RulePack 1-* RulePackItem *-1 RuleVersion          (a pack pins exact rule versions)
    ComplianceResult 1-* RuleEvaluation, 1-* Violation  (a result keeps the pack + versions it used)

Editing a rule never changes an old version: it appends a new RuleVersion, so historical results stay
interpretable (FDS 12.7, acceptance criterion "historical inspections retain the rule version context").
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Severity(models.TextChoices):
    CRITICAL = 'critical', 'Critical'
    MAJOR = 'major', 'Major'
    MINOR = 'minor', 'Minor'


class Outcome(models.TextChoices):
    """Per-rule and overall result states (FR-COMP-004)."""

    COMPLIANT = 'compliant', 'Compliant'
    NON_COMPLIANT = 'non_compliant', 'Non-Compliant'
    REQUIRES_VERIFICATION = 'requires_verification', 'Requires Verification'
    NOT_APPLICABLE = 'not_applicable', 'Not Applicable'


class RuleCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'rule categories'

    def __str__(self):
        return self.name


class ComplianceRule(models.Model):
    """Identity of a rule (stable code such as R-001). The checkable logic lives in its RuleVersions."""

    code = models.CharField(max_length=20, unique=True, help_text='Shown as Rule ID, e.g. R-001')
    title = models.CharField('rule name', max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(RuleCategory, on_delete=models.PROTECT, related_name='rules')
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MAJOR)
    regulation_ref = models.CharField(
        'regulation reference', max_length=200, blank=True, help_text='e.g. FSS (L&D) Regs 2020, Reg 5(7)'
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.title}'

    @property
    def current_version(self):
        return self.versions.filter(is_current=True).first()


class RuleVersion(models.Model):
    """One immutable revision of a rule's logic. `rule_type` + `parameters` are interpreted by
    `apps.compliance.engine.evaluator`."""

    rule = models.ForeignKey(ComplianceRule, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    rule_type = models.CharField(max_length=30)
    parameters = models.JSONField(default=dict, blank=True)
    applies_when = models.JSONField(default=list, blank=True)
    on_fail = models.CharField(
        max_length=25,
        choices=[(Outcome.NON_COMPLIANT.value, 'Non-Compliant'), (Outcome.REQUIRES_VERIFICATION.value, 'Requires Verification')],
        default=Outcome.NON_COMPLIANT,
    )
    failure_message = models.CharField(max_length=300, blank=True, help_text='Shown on the violation')
    change_note = models.CharField(max_length=255, blank=True)
    is_current = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rule__code', '-version_number']
        constraints = [models.UniqueConstraint(fields=['rule', 'version_number'], name='uniq_rule_version_number')]

    def __str__(self):
        return f'{self.rule.code} v{self.version_number}'


class PackStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    ACTIVE = 'active', 'Active'
    RETIRED = 'retired', 'Retired'


class RulePack(models.Model):
    name = models.CharField(max_length=150, unique=True)
    version = models.CharField(max_length=20, default='v1.0', help_text='Pack release label, e.g. v2.1')
    description = models.TextField(blank=True)
    applies_to = models.CharField(max_length=150, default='All packaged food', help_text='Shown in the pack list')
    product_categories = models.JSONField(
        default=list, blank=True, help_text='Product categories this pack applies to. Empty = all products.'
    )
    extends = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='extended_by',
        help_text='Also apply every rule of this pack (e.g. a category pack that builds on the basic label pack).',
    )
    regulation_ref = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=PackStatus.choices, default=PackStatus.DRAFT)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.name} ({self.version})'

    def state_on(self, day=None):
        """draft | active | scheduled | expired | retired - what the pack means on `day` (default today)."""
        day = day or timezone.localdate()
        if self.status == PackStatus.DRAFT:
            return 'draft'
        if self.status == PackStatus.RETIRED:
            return 'retired'
        if self.effective_from and self.effective_from > day:
            return 'scheduled'
        if self.effective_to and self.effective_to < day:
            return 'expired'
        return 'active'

    def covers_category(self, category: str) -> bool:
        cats = [c.strip().lower() for c in (self.product_categories or []) if str(c).strip()]
        if not cats:
            return True
        return any(c in (category or '').lower() for c in cats)


class RulePackItem(models.Model):
    pack = models.ForeignKey(RulePack, on_delete=models.CASCADE, related_name='items')
    rule = models.ForeignKey(ComplianceRule, on_delete=models.PROTECT, related_name='pack_items')
    rule_version = models.ForeignKey(RuleVersion, on_delete=models.PROTECT, related_name='pack_items')
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'rule__code']
        constraints = [models.UniqueConstraint(fields=['pack', 'rule'], name='uniq_pack_rule')]

    def __str__(self):
        return f'{self.pack.name}: {self.rule_version}'


class ComplianceResult(models.Model):
    """One evaluation run. Snapshots the pack and the verified data so it stays readable after rules change."""

    pack = models.ForeignKey(RulePack, on_delete=models.PROTECT, related_name='results')
    pack_name = models.CharField(max_length=150)
    pack_version = models.CharField(max_length=20)
    reference = models.CharField(
        max_length=100, blank=True, help_text='Free reference, e.g. an inspection number, until Inspection is linked'
    )
    reference_date = models.DateField(default=timezone.localdate, help_text='"Today" for expiry checks')
    data_snapshot = models.JSONField(default=dict)
    overall_status = models.CharField(max_length=25, choices=Outcome.choices)
    compliant_count = models.PositiveIntegerField(default=0)
    non_compliant_count = models.PositiveIntegerField(default=0)
    verification_count = models.PositiveIntegerField(default=0)
    not_applicable_count = models.PositiveIntegerField(default=0)
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='compliance_results'
    )
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-evaluated_at', '-id']

    def __str__(self):
        return f'Result #{self.pk} {self.overall_status}'


class RuleEvaluation(models.Model):
    result = models.ForeignKey(ComplianceResult, on_delete=models.CASCADE, related_name='evaluations')
    rule_version = models.ForeignKey(RuleVersion, on_delete=models.PROTECT, related_name='evaluations')
    rule_code = models.CharField(max_length=20)
    rule_title = models.CharField(max_length=200)
    category_name = models.CharField(max_length=100, blank=True)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    regulation_ref = models.CharField(max_length=200, blank=True)
    version_number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=25, choices=Outcome.choices)
    detail = models.CharField(max_length=500, blank=True)
    observed = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['rule_code']


class Violation(models.Model):
    """A Non-Compliant rule outcome (FR-COMP-002). Requires Verification is not a violation."""

    result = models.ForeignKey(ComplianceResult, on_delete=models.CASCADE, related_name='violations')
    evaluation = models.OneToOneField(RuleEvaluation, on_delete=models.CASCADE, related_name='violation')
    rule_version = models.ForeignKey(RuleVersion, on_delete=models.PROTECT, related_name='violations')
    rule_code = models.CharField(max_length=20)
    rule_title = models.CharField(max_length=200)
    category_name = models.CharField(max_length=100, blank=True)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    regulation_ref = models.CharField(max_length=200, blank=True)
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'rule_code']
