from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from inspections.models import Inspection

from .models import Report
from .pdf import MAX_IMAGES, build_pdf


class ReportError(Exception):
    """Raised when a report cannot be generated (message is user-facing)."""


# ---------------------------------------------------------------------------
# Compliance data  
# ---------------------------------------------------------------------------
def get_compliance_data(inspection):
    """
    Return the stored compliance outcome for an inspection as a plain dict:

        {
          'result': 'COMPLIANT' | 'NON_COMPLIANT' | 'REQUIRES_VERIFICATION' | 'NOT_APPLICABLE',
          'rule_pack_name': 'FSSAI Basic Label Pack',
          'rule_pack_version': 'v2.1',
          'rule_results': [{'rule': 'MRP', 'status': 'Passed', 'message': ''}, ...],
          'violations':   [{'rule': 'Net Quantity', 'message': 'Not declared'}, ...],
        }

    TODO: connect this to the Compliance Rules models (Module 4: result,
    rule pack, per-rule outcomes, Violation). Until then it returns
    REQUIRES_VERIFICATION so a report never claims "Compliant" without data.
    """
    return {
        'result': Report.Result.REQUIRES_VERIFICATION,
        'rule_pack_name': '',
        'rule_pack_version': '',
        'rule_results': [],
        'violations': [],
    }


# ---------------------------------------------------------------------------
# Context shared by the HTML preview and the PDF
# ---------------------------------------------------------------------------
def _fmt_dt(dt, long=False):
    if not dt:
        return '—'
    fmt = '%d %B %Y, %H:%M' if long else '%d %b %Y, %H:%M'
    return timezone.localtime(dt).strftime(fmt)


def _val(value, default='—'):
    return str(value) if value not in (None, '') else default


def _rule_summary(rule_results):
    """One-line summary, e.g. 'FSSAI License · MRP — all Passed'."""
    if not rule_results:
        return ''
    statuses = {str(r.get('status', '')).strip().lower() for r in rule_results}
    names = ' · '.join(r['rule'] for r in rule_results)
    if statuses == {'passed'}:
        return f"{names} — all Passed"
    return ' · '.join(f"{r['rule']} — {str(r.get('status', '')).title()}" for r in rule_results)


def build_report_context(report):
    inspection = report.inspection
    product = inspection.product
    verified = getattr(inspection, 'verified_data', None)  # None if missing
    inspector = inspection.inspector
    snap = report.snapshot or {}

    inspector_name = inspector.get_full_name() or inspector.get_username()

    brand = verified.brand if verified and verified.brand else getattr(product, 'brand', '')
    mrp = verified.mrp if verified and verified.mrp is not None else getattr(product, 'mrp', None)
    category = getattr(product, 'category', None)

    header_left = [
        ('Inspection ID', f"#{inspection.inspection_number}"),
        ('Report ID', f"#{report.report_number}"),
        ('Date', _fmt_dt(inspection.started_at, long=True)),
    ]
    header_right = [
        ('Inspector', inspector_name),
        ('Role', _val(getattr(inspector, 'role', None), 'Inspector')),
        # Inspection has no location field yet; shows '—' until one is added.
        ('Location', _val(getattr(inspection, 'location', None))),
    ]

    product_title = _val(getattr(product, 'name', product))
    product_meta1 = [
        ('Brand', _val(brand)),
        ('GTIN', _val(getattr(product, 'barcode', ''))),
    ]
    product_meta2 = [
        ('Net Qty', _val(verified.net_quantity if verified else '')),
        ('MRP', f"₹{mrp}" if mrp is not None else '—'),
        ('Category', _val(category)),
    ]

    label_lines = []
    if verified:
        label_lines = [
            [('Mfg Date', _val(verified.manufacturing_date)),
             ('Best Before', _val(verified.best_before))],
            [('FSSAI Lic', _val(verified.fssai_license)),
             ('Manufacturer', _val(verified.manufacturer))],
            [('Ingredients', _val(verified.ingredients))],
        ]
        for label, value in (
            ('Expiry Date', verified.expiry_date),
            ('Packer', verified.packer),
            ('Importer', verified.importer),
            ('Other Declarations', verified.other_declarations),
        ):
            if value:
                label_lines.append([(label, value)])

    violations = snap.get('violations', [])
    rule_results = snap.get('rule_results', [])
    result = report.result
    pack = ' '.join(x for x in (report.rule_pack_name, report.rule_pack_version) if x)
    in_pack = f" in {pack}" if pack else ''

    if result == Report.Result.COMPLIANT:
        summary = f"All applicable rules{in_pack} passed. No violations recorded."
    elif result == Report.Result.NON_COMPLIANT:
        summary = f"{len(violations)} violation(s) recorded{in_pack}. See details below."
    elif result == Report.Result.NOT_APPLICABLE:
        summary = 'No applicable rules for this product.'
    else:
        summary = 'Some information could not be confirmed. Manual verification is required.'

    images = []
    for img in inspection.images.all().order_by('sequence')[:MAX_IMAGES]:
        try:
            path = img.image.path
        except Exception:
            path = ''
        images.append({'label': img.get_image_type_display(), 'path': path, 'url': img.image.url})

    return {
        'report_number': report.report_number,
        'header_left': header_left,
        'header_right': header_right,
        'product_title': product_title,
        'product_meta1': product_meta1,
        'product_meta2': product_meta2,
        'label_lines': label_lines,
        'result': result,
        'result_label': report.get_result_display(),
        'summary_text': summary,
        'rule_summary': _rule_summary(rule_results),
        'violations': violations,
        'remarks': inspection.remarks or '',
        'images': images,
    }


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
@transaction.atomic
def create_report(inspection, user):
    if inspection.status != Inspection.Status.COMPLETED:
        raise ReportError('Report can be generated only for completed inspections.')

    verified = getattr(inspection, 'verified_data', None)
    if verified is None or not verified.is_verified:
        raise ReportError('Inspector verification is pending for this inspection.')

    if Report.objects.filter(inspection=inspection).exists():
        raise ReportError('A report already exists for this inspection.')

    compliance = get_compliance_data(inspection)
    report = Report.objects.create(
        report_number=f"RPT-{inspection.pk}",
        inspection=inspection,
        generated_by=user,
        result=compliance['result'],
        rule_pack_name=compliance.get('rule_pack_name', ''),
        rule_pack_version=compliance.get('rule_pack_version', ''),
        snapshot={
            'rule_results': compliance.get('rule_results', []),
            'violations': compliance.get('violations', []),
        },
    )

    pdf_bytes = build_pdf(build_report_context(report))
    report.pdf_file.save(f"{report.report_number}.pdf", ContentFile(pdf_bytes), save=True)
    return report