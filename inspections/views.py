from django.shortcuts import render, redirect
from inspections.forms import InspectionForm

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