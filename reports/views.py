import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inspections.models import Inspection

from .models import Report
from .services import ReportError, build_report_context, create_report


def _reports():
    return Report.objects.select_related(
        'inspection', 'inspection__product', 'inspection__inspector', 'generated_by'
    )


def _inspections():
    return Inspection.objects.select_related('product', 'inspector')


# ------------------------------- Report List -------------------------------
def report_list(request):
    reports = _reports()

    q = request.GET.get('q', '').strip()
    result = request.GET.get('result', '').strip()
    date = request.GET.get('date', '').strip()

    if q:
        reports = reports.filter(
            Q(report_number__icontains=q)
            | Q(inspection__inspection_number__icontains=q)
            | Q(inspection__product__name__icontains=q)
        )
    if result:
        reports = reports.filter(result=result)
    if date:
        try:
            reports = reports.filter(generated_at__date=datetime.date.fromisoformat(date))
        except ValueError:
            date = ''

    return render(request, 'reports/report_list.html', {
        'reports': reports,
        'result_choices': Report.Result.choices,
        'q': q,
        'selected_result': result,
        'date': date,
    })


# ------------------------------ Generate Report ------------------------------
def report_generate_list(request):
    """Completed inspections that do not have a report yet."""
    inspections = (
        _inspections()
        .filter(status=Inspection.Status.COMPLETED, report__isnull=True)
        .order_by('-completed_at', '-created_at')
    )
    return render(request, 'reports/report_generate.html', {'inspections': inspections})



@require_POST
def report_generate(request, inspection_pk):
    inspection = get_object_or_404(_inspections(), pk=inspection_pk)
    try:
        report = create_report(inspection, request.user)
    except ReportError as exc:
        messages.error(request, str(exc))
        return redirect('reports:report_generate_list')
    except Exception:
        messages.error(request, 'Report generation failed. Please try again.')
        return redirect('reports:report_generate_list')

    messages.success(request, f"Report {report.report_number} generated.")
    return redirect('reports:report_preview', pk=report.pk)


# ------------------------------ Preview / Print ------------------------------
def report_preview(request, pk):
    report = get_object_or_404(_reports(), pk=pk)
    return render(request, 'reports/report_preview.html', {
        'selected': report,
        'ctx': build_report_context(report),
    })


# --------------------------------- Download ---------------------------------
def report_download(request, pk):
    report = get_object_or_404(_reports(), pk=pk)
    return FileResponse(
        report.pdf_file.open('rb'),
        as_attachment=True,
        filename=f"{report.report_number}.pdf",
        content_type='application/pdf',
    )