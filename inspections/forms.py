from .models import Inspection, InspectionImage, VerifiedInspectionData
from django import forms

class InspectionForm(forms.ModelForm):
    class Meta:
        model = Inspection
        fields = '__all__'

class VerifiedInspectionDataForm(forms.ModelForm):
    class Meta:
        model = VerifiedInspectionData
        fields = '__all__'


class InspectionImageForm(forms.ModelForm):
    class Meta:
        model = InspectionImage
        fields = '__all__'