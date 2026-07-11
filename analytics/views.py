from django.shortcuts import render


def dashboard(request):
    # Fleshed out in Step 7 with KPI tiles, upload form, and the ask-box.
    return render(request, "analytics/dashboard.html")
