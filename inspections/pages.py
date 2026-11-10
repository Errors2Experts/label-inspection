from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def inspection_page(request):
    return render(request, "inspections/inspection.html")