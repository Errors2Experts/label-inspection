from django.contrib import admin

from .models import *

admin.site.register(Inspection)
admin.site.register(InspectionImage)
admin.site.register(OCRResult)
admin.site.register(AIAnalysis)
admin.site.register(VerifiedInspectionData)
