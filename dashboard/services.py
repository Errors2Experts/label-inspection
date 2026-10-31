"""
Numbers for the Dashboard page.

Compliance outcome comes from the Report record (it stores the result frozen
at generation time). Until Module 4 is wired into reports.services, every
report is "Requires Verification", so those inspections show under Review.
"""
from collections import Counter
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from inspections.models import Inspection
from reports.models import Report

# Inspection has left the inspector's hands but has no final report yet.
# Plain strings (not Inspection.Status.X) so a renamed enum member can't break this.
REVIEW_STATUSES = ['VERIFICATION_PENDING', 'VERIFIED', 'EVALUATING', 'COMPLETED']

# Report.result -> (label, css class)
_REPORT_BADGES = {
    Report.Result.COMPLIANT: ('Compliant', 'compliant'),
    Report.Result.NON_COMPLIANT: ('Non-Compliant', 'non_compliant'),
    Report.Result.REQUIRES_VERIFICATION: ('Review', 'review'),
    Report.Result.NOT_APPLICABLE: ('Not Applicable', 'neutral'),
}


def _pct(part, total):
    return round(part * 100 / total) if total else 0


def _badge(inspection):
    """(label, css class) for one inspection row."""
    report = getattr(inspection, 'report', None)  # None when no report exists
    if report is not None:
        return _REPORT_BADGES.get(report.result, ('Review', 'review'))
    if inspection.status in REVIEW_STATUSES:
        return 'Review', 'review'
    return inspection.get_status_display(), 'neutral'


def _top_violations(limit):
    counts = Counter()
    for snapshot in Report.objects.values_list('snapshot', flat=True):
        for v in (snapshot or {}).get('violations', []):
            name = (v.get('message') or v.get('rule') or '').strip()
            if name:
                counts[name] += 1
    return [{'name': n, 'count': c} for n, c in counts.most_common(limit)]


def get_dashboard_data(recent_limit=5, violation_limit=5):
    week_ago = timezone.now() - timedelta(days=7)

    agg = Inspection.objects.aggregate(
        total=Count('id'),
        this_week=Count('id', filter=Q(started_at__gte=week_ago)),
        compliant=Count('id', filter=Q(report__result=Report.Result.COMPLIANT)),
        non_compliant=Count('id', filter=Q(report__result=Report.Result.NON_COMPLIANT)),
        review=Count('id', filter=(
            Q(report__result=Report.Result.REQUIRES_VERIFICATION)
            | Q(report__isnull=True, status__in=REVIEW_STATUSES)
        )),
    )
    total = agg['total']

    cards = [
        {'label': 'Total Inspections', 'value': total,
         'sub': f"↑ {agg['this_week']} this week", 'tone': 'total'},
        {'label': 'Compliant', 'value': agg['compliant'],
         'sub': f"{_pct(agg['compliant'], total)}%", 'tone': 'compliant'},
        {'label': 'Non-Compliant', 'value': agg['non_compliant'],
         'sub': f"{_pct(agg['non_compliant'], total)}%", 'tone': 'non_compliant'},
        {'label': 'Needs Review', 'value': agg['review'],
         'sub': f"{_pct(agg['review'], total)}%", 'tone': 'review'},
    ]

    recent = []
    qs = (Inspection.objects.select_related('product', 'report')
          .order_by('-created_at')[:recent_limit])
    for i in qs:
        label, css = _badge(i)
        recent.append({
            'number': i.inspection_number,
            'product': getattr(i.product, 'name', str(i.product)),
            'status_label': label,
            'status_class': css,
            'date': timezone.localtime(i.started_at).strftime('%d %b'),
        })

    violations = _top_violations(violation_limit)
    top = violations[0]['count'] if violations else 0
    for v in violations:
        v['bar'] = round(v['count'] * 100 / top) if top else 0

    return {'cards': cards, 'recent': recent, 'violations': violations}