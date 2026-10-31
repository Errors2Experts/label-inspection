from django.shortcuts import render, redirect
from inspections.forms import InspectionForm, InspectionImageForm, VerifiedInspectionDataForm

# Create your views here.
def inspection_create(request):
    if request.method == 'POST':
        form = InspectionForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            return redirect('inspection_success')

    else:
        form = InspectionForm()

    return render(request, 'inspection_form.html', {'form': form})

def verified_inspection_data_create(request):
    if request.method == 'POST':
        form = VerifiedInspectionDataForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            return redirect('verified_inspection_success')

    else:
        form = VerifiedInspectionDataForm()

    return render(request, 'verified_inspection_form.html', {'form': form})

def inspection_image_upload(request):
    if request.method == 'POST':
        form = InspectionImageForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            return redirect('inspection_image_success')

    else:
        form = InspectionImageForm()

    return render(request, 'inspection_image_form.html', {'form': form})