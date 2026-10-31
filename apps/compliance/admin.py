from django.contrib import admin

from .models import (
    ComplianceResult,
    ComplianceRule,
    RuleCategory,
    RuleEvaluation,
    RulePack,
    RulePackItem,
    RuleVersion,
    Violation,
)


class RuleVersionInline(admin.TabularInline):
    model = RuleVersion
    extra = 0
    fields = ('version_number', 'rule_type', 'on_fail', 'is_current', 'change_note')
    readonly_fields = fields
    can_delete = False


@admin.register(ComplianceRule)
class ComplianceRuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'category', 'severity', 'is_active')
    list_filter = ('category', 'severity', 'is_active')
    search_fields = ('code', 'title', 'regulation_ref')
    inlines = [RuleVersionInline]


class RulePackItemInline(admin.TabularInline):
    model = RulePackItem
    extra = 0
    raw_id_fields = ('rule', 'rule_version')


@admin.register(RulePack)
class RulePackAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'status', 'effective_from', 'effective_to')
    list_filter = ('status',)
    inlines = [RulePackItemInline]


class EvaluationInline(admin.TabularInline):
    model = RuleEvaluation
    extra = 0
    can_delete = False
    readonly_fields = ('rule_code', 'rule_title', 'severity', 'version_number', 'outcome', 'detail')
    exclude = ('rule_version', 'category_name', 'regulation_ref', 'observed')


@admin.register(ComplianceResult)
class ComplianceResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'pack_name', 'pack_version', 'reference', 'overall_status', 'evaluated_by', 'evaluated_at')
    list_filter = ('overall_status',)
    inlines = [EvaluationInline]


admin.site.register(RuleCategory)
admin.site.register(Violation)
