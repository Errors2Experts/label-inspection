from .models import Inspection
from django import forms

class InspectionForm(forms.ModelForm):
    class Meta:
        model = Inspection
        fields = '__all__'