import re

from rest_framework import serializers

from . import services
from .engine.evaluator import DATA_FIELDS, validate_rule_config
from .models import (
    ComplianceResult,
    ComplianceRule,
    Outcome,
    RuleCategory,
    RuleEvaluation,
    RulePack,
    RulePackItem,
    RuleVersion,
    Violation,
)

CODE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{1,19}$')


class RuleCategorySerializer(serializers.ModelSerializer):
    rule_count = serializers.SerializerMethodField()

    class Meta:
        model = RuleCategory
        fields = ['id', 'name', 'description', 'is_active', 'rule_count']

    def get_rule_count(self, obj):
        return obj.rules.count()

    def validate_name(self, value):
        value = ' '.join(value.split())
        if not value:
            raise serializers.ValidationError('Name is required.')
        clash = RuleCategory.objects.filter(name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value


class RuleVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    rule_code = serializers.CharField(source='rule.code', read_only=True)

    class Meta:
        model = RuleVersion
        fields = [
            'id', 'rule', 'rule_code', 'version_number', 'rule_type', 'parameters', 'applies_when', 'on_fail',
            'failure_message', 'change_note', 'is_current', 'created_by_name', 'created_at',
        ]  # fmt: skip

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else ''


class RuleSerializer(serializers.ModelSerializer):
    """A rule together with its *current* version's logic. Saving changed logic appends a new version."""

    category_name = serializers.CharField(source='category.name', read_only=True)
    code = serializers.CharField(required=False, allow_blank=True, max_length=20)
    rule_type = serializers.CharField()
    parameters = serializers.JSONField(required=False)
    applies_when = serializers.JSONField(required=False)
    on_fail = serializers.ChoiceField(
        choices=[Outcome.NON_COMPLIANT.value, Outcome.REQUIRES_VERIFICATION.value], required=False
    )
    failure_message = serializers.CharField(required=False, allow_blank=True, max_length=300)
    change_note = serializers.CharField(required=False, allow_blank=True, max_length=255, write_only=True)
    version_number = serializers.SerializerMethodField()
    pack_count = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceRule
        fields = [
            'id', 'code', 'title', 'description', 'category', 'category_name', 'severity', 'regulation_ref',
            'is_active', 'rule_type', 'parameters', 'applies_when', 'on_fail', 'failure_message', 'change_note',
            'version_number', 'pack_count', 'updated_at',
        ]  # fmt: skip
        read_only_fields = ['updated_at']

    def to_representation(self, instance):
        # The logic fields live on the current RuleVersion; expose them on the rule as plain attributes first.
        version = instance.current_version
        for key in services.CONFIG_KEYS:
            setattr(instance, key, getattr(version, key) if version else ({} if key == 'parameters' else [] if key == 'applies_when' else ''))
        return super().to_representation(instance)

    def get_version_number(self, obj):
        v = obj.current_version
        return v.version_number if v else None

    def get_pack_count(self, obj):
        return obj.pack_items.count()

    # -- validation
    def validate_code(self, value):
        value = (value or '').strip().upper()
        if not value:
            return value
        if not CODE_RE.match(value):
            raise serializers.ValidationError('Use letters, digits, dot, dash or underscore (2-20 characters).')
        clash = ComplianceRule.objects.filter(code__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError('This Rule ID is already in use.')
        return value

    def validate_title(self, value):
        value = ' '.join(value.split())
        if not value:
            raise serializers.ValidationError('Rule name is required.')
        return value

    def validate(self, attrs):
        current = self.instance.current_version if self.instance else None
        merged = {
            'rule_type': attrs.get('rule_type', current.rule_type if current else None),
            'parameters': attrs.get('parameters', current.parameters if current else {}),
            'applies_when': attrs.get('applies_when', current.applies_when if current else []),
            'on_fail': attrs.get('on_fail', current.on_fail if current else Outcome.NON_COMPLIANT),
        }
        problems = validate_rule_config(**merged)
        if problems:
            raise serializers.ValidationError({'parameters': problems})
        return attrs

    # -- persistence
    def _config(self, validated, current):
        base = services.config_of(current) if current else {}
        return {k: validated.get(k, base.get(k)) for k in services.CONFIG_KEYS}

    def create(self, validated):
        user = self.context['request'].user
        note = validated.pop('change_note', '') or 'Initial version'
        config = self._config(validated, None)
        config['parameters'] = config['parameters'] or {}
        config['applies_when'] = config['applies_when'] or []
        config['on_fail'] = config['on_fail'] or Outcome.NON_COMPLIANT
        config['failure_message'] = config['failure_message'] or ''
        for key in services.CONFIG_KEYS:
            validated.pop(key, None)
        if not validated.get('code'):
            validated['code'] = next_rule_code()
        rule = ComplianceRule.objects.create(created_by=user, **validated)
        services.add_version(rule, config, user, note)
        return rule

    def update(self, instance, validated):
        user = self.context['request'].user
        note = validated.pop('change_note', '')
        current = instance.current_version
        config = self._config(validated, current)
        for key in services.CONFIG_KEYS:
            validated.pop(key, None)
        if 'code' in validated and not validated['code']:
            validated.pop('code')
        for attr, value in validated.items():
            setattr(instance, attr, value)
        instance.save()
        if services.config_changed(current, config):
            services.add_version(instance, config, user, note or 'Updated rule logic')
        return instance


def next_rule_code() -> str:
    numbers = [
        int(m.group(1))
        for code in ComplianceRule.objects.filter(code__startswith='R-').values_list('code', flat=True)
        if (m := re.match(r'^R-(\d+)$', code))
    ]
    return f'R-{(max(numbers) if numbers else 0) + 1:03d}'


class PackItemSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source='rule.code', read_only=True)
    title = serializers.CharField(source='rule.title', read_only=True)
    category_name = serializers.CharField(source='rule.category.name', read_only=True)
    severity = serializers.CharField(source='rule.severity', read_only=True)
    is_active = serializers.BooleanField(source='rule.is_active', read_only=True)
    version_number = serializers.IntegerField(source='rule_version.version_number', read_only=True)
    latest_version = serializers.SerializerMethodField()

    class Meta:
        model = RulePackItem
        fields = [
            'id', 'rule', 'rule_version', 'code', 'title', 'category_name', 'severity', 'is_active',
            'version_number', 'latest_version',
        ]  # fmt: skip

    def get_latest_version(self, obj):
        v = obj.rule.current_version
        return v.version_number if v else None


class RulePackSerializer(serializers.ModelSerializer):
    rule_count = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    items = PackItemSerializer(many=True, read_only=True)
    extends_name = serializers.SerializerMethodField()

    class Meta:
        model = RulePack
        fields = [
            'id', 'name', 'version', 'description', 'applies_to', 'product_categories', 'extends', 'extends_name',
            'regulation_ref', 'status', 'state', 'effective_from', 'effective_to', 'rule_count', 'items', 'updated_at',
        ]  # fmt: skip
        read_only_fields = ['updated_at']

    def get_rule_count(self, obj):
        return obj.items.count()

    def get_state(self, obj):
        return obj.state_on()

    def get_extends_name(self, obj):
        return f'{obj.extends.name} ({obj.extends.version})' if obj.extends_id else ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get('brief'):
            data.pop('items', None)
        return data

    def validate_product_categories(self, value):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise serializers.ValidationError('Provide a list of category names.')
        return [v.strip() for v in value if v.strip()]

    def validate_name(self, value):
        value = ' '.join(value.split())
        clash = RulePack.objects.filter(name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError('A rule pack with this name already exists.')
        return value

    def validate_extends(self, value):
        if value is None:
            return value
        if self.instance and value.pk == self.instance.pk:
            raise serializers.ValidationError('A pack cannot extend itself.')
        if value.extends_id:
            raise serializers.ValidationError('Choose a pack that does not itself extend another pack.')
        if self.instance and self.instance.extended_by.exists():
            raise serializers.ValidationError('Other packs build on this one, so it cannot extend a pack itself.')
        return value

    def validate(self, attrs):
        start = attrs.get('effective_from', getattr(self.instance, 'effective_from', None))
        end = attrs.get('effective_to', getattr(self.instance, 'effective_to', None))
        if start and end and end < start:
            raise serializers.ValidationError({'effective_to': 'Must not be before the effective-from date.'})
        return attrs

    def create(self, validated):
        return RulePack.objects.create(created_by=self.context['request'].user, **validated)


class RuleEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleEvaluation
        fields = [
            'id', 'rule_code', 'rule_title', 'category_name', 'severity', 'regulation_ref', 'version_number',
            'outcome', 'detail', 'observed',
        ]  # fmt: skip


class ViolationSerializer(serializers.ModelSerializer):
    result_id = serializers.IntegerField(source='result.id', read_only=True)
    pack_name = serializers.CharField(source='result.pack_name', read_only=True)
    reference = serializers.CharField(source='result.reference', read_only=True)
    version_number = serializers.IntegerField(source='rule_version.version_number', read_only=True)

    class Meta:
        model = Violation
        fields = [
            'id', 'result_id', 'pack_name', 'reference', 'rule_code', 'rule_title', 'category_name', 'severity',
            'regulation_ref', 'version_number', 'message', 'created_at',
        ]  # fmt: skip


class ComplianceResultSerializer(serializers.ModelSerializer):
    evaluated_by_name = serializers.SerializerMethodField()
    evaluations = RuleEvaluationSerializer(many=True, read_only=True)
    violations = ViolationSerializer(many=True, read_only=True)

    class Meta:
        model = ComplianceResult
        fields = [
            'id', 'pack', 'pack_name', 'pack_version', 'reference', 'reference_date', 'data_snapshot',
            'overall_status', 'compliant_count', 'non_compliant_count', 'verification_count',
            'not_applicable_count', 'evaluated_by_name', 'evaluated_at', 'evaluations', 'violations',
        ]  # fmt: skip

    def get_evaluated_by_name(self, obj):
        return obj.evaluated_by.full_name if obj.evaluated_by else ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get('brief'):
            data.pop('evaluations', None)
            data.pop('violations', None)
            data.pop('data_snapshot', None)
        return data


class EvaluateRequestSerializer(serializers.Serializer):
    data = serializers.DictField(child=serializers.JSONField(allow_null=True))
    pack = serializers.PrimaryKeyRelatedField(queryset=RulePack.objects.all(), required=False, allow_null=True)
    category = serializers.CharField(required=False, allow_blank=True, max_length=150)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=100)
    reference_date = serializers.DateField(required=False)

    def validate_data(self, value):
        unknown = sorted(set(value) - set(DATA_FIELDS))
        if unknown:
            raise serializers.ValidationError(f'Unknown fields: {", ".join(unknown)}.')
        if not any(str(v or '').strip() for v in value.values()):
            raise serializers.ValidationError('Provide at least one verified label field.')
        return value

