from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from .services import PrepBusinessAPI
def index(request):
    return render(request, 'prep_management/index.html')
def open_shipments(request):
    api = PrepBusinessAPI(settings.PREP_BUSINESS_API_KEY)
    data = api.get_open_inbound_shipments()
    return JsonResponse(data, safe=False)
