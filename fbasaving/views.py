# /var/www/html/webapps/projects/prep_center/fbasaving/views.py

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .file_processing import file_processing  # Importa la funzione dal file corretto
import logging

logger = logging.getLogger(__name__)

def home(request):
    return render(request, 'fbasaving/fbasaving.html')

@csrf_exempt
def upload_file_view(request):
    if request.method == 'POST':
        try:
            file = request.FILES['file']
            results = file_processing(file)
            
            required_keys = ['total_amazon_cost', 'total_prep_center_cost', 'saving', 'saving_percentage', 'table_data']
            for key in required_keys:
                if key not in results:
                    raise KeyError(f"Chiave mancante nella risposta: {key}")
            
            return JsonResponse(results)
        except KeyError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
