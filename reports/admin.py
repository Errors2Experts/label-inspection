from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('report_number', 'inspection', 'result', 'generated_by', 'generated_at')
    list_filter = ('result',)
    search_fields = ('report_number', 'inspection__inspection_number')