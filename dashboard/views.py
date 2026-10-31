from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import get_dashboard_data


def dashboard(request):
    return render(request, 'dashboard.html', get_dashboard_data())