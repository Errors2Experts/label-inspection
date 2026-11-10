from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from inspections.models import Inspection

# Create your views here.

def history_evidence(request):
    data = (
        Inspection.objects
        .select_related("product", "inspector")
        .order_by("-created_at")
    )

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    date = request.GET.get("date", "").strip()

    if q:
        data = data.filter(
            Q(inspection_number__icontains=q)
            | Q(product__name__icontains=q)
            | Q(product__barcode__icontains=q)
        )
    if status:
        data = data.filter(status=status)
    if date:
        data = data.filter(created_at__date=date)

    return render(request, "history/history.html", {
        "data": data,
        "status_choices": Inspection.Status.choices,
    })


def inspection_detail(request, pk):
    inspection = get_object_or_404(
        Inspection.objects
        .select_related("product", "inspector", "verified_data")
        .prefetch_related("images"),
        pk=pk,
    )
    return render(request, "history/inspection_detail.html", {
        "inspection": inspection,
    })