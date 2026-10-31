from django.contrib import admin
from .models import Inspection, InspectionImage, VerifiedInspectionData

# Register your models here.
admin.site.register(Inspection)
admin.site.register(VerifiedInspectionData)
admin.site.register(InspectionImage)

