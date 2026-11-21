from django.conf import settings
from django.db import models


# ================================ REPORT MODEL ================================
class Report(models.Model):

    class Result(models.TextChoices):
        COMPLIANT = 'COMPLIANT', 'Compliant'
        NON_COMPLIANT = 'NON_COMPLIANT', 'Non-Compliant'
        REQUIRES_VERIFICATION = 'REQUIRES_VERIFICATION', 'Requires Verification'
        NOT_APPLICABLE = 'NOT_APPLICABLE', 'Not Applicable'

    report_number = models.CharField(max_length=30, unique=True)
    inspection = models.OneToOneField(
        'inspections.Inspection', on_delete=models.PROTECT, related_name='report'
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='generated_reports'
    )
    result = models.CharField(max_length=30, choices=Result.choices)
    rule_pack_name = models.CharField(max_length=255, blank=True)
    rule_pack_version = models.CharField(max_length=50, blank=True)

    # Compliance data frozen at generation time, so the report always matches
    # what was true when it was generated (rule versions can change later).
    snapshot = models.JSONField(default=dict, blank=True)

    pdf_file = models.FileField(upload_to='reports/%Y/%m/')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return self.report_number