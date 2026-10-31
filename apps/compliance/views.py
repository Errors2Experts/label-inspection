"""Compliance Rules REST API (FDS 12.6). Rule management is Admin/Supervisor only (FDS 7.2);
evaluation and results are open to every role so the Inspection module can call them."""

import re

from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAdminOrSupervisor, IsAnyRole

from . import services
from .engine.evaluator import DATA_FIELDS, RULE_TYPES
from .models import (
    ComplianceResult,
    ComplianceRule,
    Outcome,
    PackStatus,
    RuleCategory,
    RulePack,
    Severity,
    Violation,
)
from .serializers import (
    ComplianceResultSerializer,
    EvaluateRequestSerializer,
    RuleCategorySerializer,
    RulePackSerializer,
    RuleSerializer,
    RuleVersionSerializer,
    ViolationSerializer,
)

MAX_SEARCH = 100


def clean_term(raw):
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', raw or '')
    return re.sub(r'\s+', ' ', text).strip()[:MAX_SEARCH]


def protected_response(exc: ProtectedError, what: str):
    return Response(
        {'detail': f'This {what} is in use (packs, versions or past results refer to it), so it cannot be deleted. '
                   'Deactivate or retire it instead.'},
        status=status.HTTP_409_CONFLICT,
    )  # fmt: skip


class RuleCategoryViewSet(viewsets.ModelViewSet):
    """/api/rule-categories/ - CRUD. A category with rules cannot be deleted."""

    queryset = RuleCategory.objects.all()
    serializer_class = RuleCategorySerializer
    permission_classes = [IsAdminOrSupervisor]
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            return protected_response(exc, 'category')


class RuleViewSet(viewsets.ModelViewSet):
    """/api/rules/ - list/search, detail, create, update (appends a version), delete (only if never used).

    Filters: ?q=  ?category=<id>  ?severity=  ?active=true|false  ?pack=<id> (rules in that pack)
    """

    queryset = ComplianceRule.objects.select_related('category')
    serializer_class = RuleSerializer
    permission_classes = [IsAdminOrSupervisor]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('versions')
        p = self.request.query_params
        term = clean_term(p.get('q'))
        if term:
            qs = qs.filter(Q(code__icontains=term) | Q(title__icontains=term) | Q(regulation_ref__icontains=term))
        if p.get('category', '').isdigit():
            qs = qs.filter(category_id=int(p['category']))
        if p.get('severity') in Severity.values:
            qs = qs.filter(severity=p['severity'])
        if p.get('active') in ('true', 'false'):
            qs = qs.filter(is_active=p['active'] == 'true')
        if p.get('pack', '').isdigit():
            qs = qs.filter(pack_items__pack_id=int(p['pack']))
        return qs

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            return protected_response(exc, 'rule')

    @action(detail=True, methods=['get'], pagination_class=None)
    def versions(self, request, pk=None):
        """GET /api/rules/{id}/versions/ - full revision history, newest first."""
        rule = self.get_object()
        qs = rule.versions.select_related('created_by', 'rule').order_by('-version_number')
        return Response(RuleVersionSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='meta')
    def meta(self, request):
        """GET /api/rules/meta/ - choices for the rule form (types, data fields, severities)."""
        return Response(
            {
                'rule_types': sorted(RULE_TYPES),
                'data_fields': DATA_FIELDS,
                'severities': [{'value': v, 'label': label} for v, label in Severity.choices],
                'categories': RuleCategorySerializer(RuleCategory.objects.filter(is_active=True), many=True).data,
            }
        )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """GET /api/rules/summary/ - the three header counts on the Compliance Rules page."""
        return Response(
            {
                'active_rules': ComplianceRule.objects.filter(is_active=True).count(),
                'rule_packs': RulePack.objects.exclude(status=PackStatus.RETIRED).count(),
                'categories': RuleCategory.objects.filter(is_active=True).count(),
            }
        )


class RulePackViewSet(viewsets.ModelViewSet):
    """/api/rule-packs/ - CRUD plus add-rule / remove-rule / refresh (re-pin to latest rule versions)."""

    queryset = RulePack.objects.prefetch_related('items__rule__category', 'items__rule_version', 'items__rule__versions')
    serializer_class = RulePackSerializer
    permission_classes = [IsAdminOrSupervisor]
    pagination_class = None

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['brief'] = self.action == 'list'
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('status') in PackStatus.values:
            qs = qs.filter(status=self.request.query_params['status'])
        return qs

    def destroy(self, request, *args, **kwargs):
        pack = self.get_object()
        if pack.results.exists():
            return Response(
                {'detail': 'This pack has been used in evaluations. Retire it instead of deleting it.'},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    def _fresh(self, pack):
        pack = self.get_queryset().get(pk=pack.pk)
        return Response(self.get_serializer(pack).data)

    @action(detail=True, methods=['post'], url_path='add-rule')
    def add_rule(self, request, pk=None):
        """POST {rule: id, version?: id}. Adds the rule (current version) or re-pins it to another version."""
        pack = self.get_object()
        try:
            rule = ComplianceRule.objects.get(pk=request.data.get('rule'))
        except (ComplianceRule.DoesNotExist, ValueError, TypeError):
            return Response({'rule': ['Choose an existing rule.']}, status=status.HTTP_400_BAD_REQUEST)
        version = None
        if request.data.get('version'):
            version = rule.versions.filter(pk=request.data['version']).first()
            if version is None:
                return Response({'version': ['That version does not belong to the rule.']}, status=400)
        try:
            services.set_pack_rule(pack, rule, version)
        except services.ComplianceError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._fresh(pack)

    @action(detail=True, methods=['post'], url_path='remove-rule')
    def remove_rule(self, request, pk=None):
        """POST {rule: id}."""
        pack = self.get_object()
        deleted, _ = pack.items.filter(rule_id=request.data.get('rule') or 0).delete()
        if not deleted:
            return Response({'rule': ['That rule is not in this pack.']}, status=status.HTTP_400_BAD_REQUEST)
        return self._fresh(pack)

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """POST - re-pin every rule in the pack to its latest version."""
        pack = self.get_object()
        changed = services.refresh_pack(pack)
        resp = self._fresh(pack)
        resp.data['refreshed'] = changed
        return resp


class ComplianceResultViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """/api/compliance/results/ - Admin/Supervisor see all runs; an Inspector sees only their own."""

    serializer_class = ComplianceResultSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = ComplianceResult.objects.select_related('evaluated_by').prefetch_related('evaluations', 'violations')
        user = self.request.user
        if user.role == Role.INSPECTOR:
            qs = qs.filter(evaluated_by=user)
        p = self.request.query_params
        if p.get('status') in Outcome.values:
            qs = qs.filter(overall_status=p['status'])
        term = clean_term(p.get('q'))
        if term:
            qs = qs.filter(Q(reference__icontains=term) | Q(pack_name__icontains=term))
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['brief'] = self.action == 'list'
        return ctx


class ViolationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """/api/compliance/violations/?severity=&rule=<code>&q=  (inspectors: own evaluations only)"""

    serializer_class = ViolationSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = Violation.objects.select_related('result', 'rule_version')
        user = self.request.user
        if user.role == Role.INSPECTOR:
            qs = qs.filter(result__evaluated_by=user)
        p = self.request.query_params
        if p.get('severity') in Severity.values:
            qs = qs.filter(severity=p['severity'])
        if clean_term(p.get('rule')):
            qs = qs.filter(rule_code__iexact=clean_term(p['rule']))
        term = clean_term(p.get('q'))
        if term:
            qs = qs.filter(Q(rule_title__icontains=term) | Q(message__icontains=term) | Q(result__reference__icontains=term))
        return qs


@api_view(['POST'])
@permission_classes([IsAnyRole])
def evaluate_view(request):
    """POST /api/compliance/evaluate/

    {"data": {<verified label fields>}, "pack": id?, "category": "Dairy"?, "reference": "INS-001"?, "reference_date": "2026-10-29"?}

    Evaluates *verified* data. With no `pack`, the active pack for today (and `category`) is used.
    Returns the stored ComplianceResult with per-rule outcomes and violations.
    """
    ser = EvaluateRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    v = ser.validated_data
    pack = v.get('pack')
    if pack is None:
        pack = services.select_pack(v.get('category', ''), v.get('reference_date'))
        if pack is None:
            return Response(
                {'detail': 'No active rule pack applies. Ask an Admin to activate one, or choose a pack.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif pack.status == PackStatus.DRAFT:
        return Response({'pack': ['Draft packs cannot be used for evaluation.']}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = services.evaluate(
            v['data'], pack, request.user, v.get('reference', ''), v.get('reference_date')
        )
    except services.ComplianceError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    result = ComplianceResult.objects.prefetch_related('evaluations', 'violations').get(pk=result.pk)
    return Response(ComplianceResultSerializer(result).data, status=status.HTTP_201_CREATED)

