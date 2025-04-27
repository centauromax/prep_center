from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging
import json
import os.path
from django.utils import translation
from .models import PictureCheck, Cliente
from .serializers import PictureCheckSerializer, ClienteSerializer
import re

# Configura il logger
logger = logging.getLogger('picture_check')

# Costante per la chiave di sessione della lingua
LANGUAGE_SESSION_KEY = 'django_language'

def home(request):
    """
    View principale per l'app picture_check
    """
    # Forza l'uso dell'italiano per questa app
    translation.activate('it')
    request.session[LANGUAGE_SESSION_KEY] = 'it'
    
    context = {
        'app_name': 'Picture Check',
    }
    return render(request, 'picture_check/picture_check.html', context)

@api_view(['GET'])
def get_clienti(request):
    """
    Ottiene la lista dei clienti attivi
    """
    try:
        # Forza l'uso dell'italiano
        translation.activate('it')
        
        clienti = Cliente.objects.filter(attivo=True)
        serializer = ClienteSerializer(clienti, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Errore nel recupero dei clienti: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def check_ean(request, ean):
    """
    Verifica se per un determinato EAN/FNSKU e Cliente sono già state fatte le foto
    """
    try:
        # Forza l'uso dell'italiano
        translation.activate('it')
        
        cliente = request.GET.get('cliente', '').strip()
        if not cliente:
            return Response({
                "ean": ean,
                "foto_da_fare": False,
                "messaggio": "Cliente non specificato."
            }, status=status.HTTP_400_BAD_REQUEST)
        # Controllo validità EAN/FNSKU: numerico, 12 o 13 cifre oppure alfanumerico, 10 caratteri
        if not (re.fullmatch(r'\d{12,13}', ean) or re.fullmatch(r'[A-Za-z0-9]{10}', ean)):
            return Response({
                "ean": ean,
                "foto_da_fare": False,
                "messaggio": "Codice EAN/FNSKU non valido: deve essere una stringa numerica di 12 o 13 cifre o alfanumerica di 10 caratteri."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verifica se la combinazione EAN/FNSKU + Cliente esiste già nel database
        ean_esistente = PictureCheck.objects.filter(ean=ean, cliente=cliente).exists()
        
        if ean_esistente:
            return Response({
                "ean": ean,
                "foto_da_fare": False,
                "messaggio": "Foto già realizzate per questo prodotto e cliente."
            })
        else:
            return Response({
                "ean": ean,
                "foto_da_fare": True,
                "messaggio": "Foto da realizzare per questo prodotto e cliente."
            })
    except Exception as e:
        logger.error(f"Errore nella verifica dell'EAN {ean}: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def salva_ean(request):
    """
    Salva un nuovo EAN per cui le foto non sono state fatte
    """
    try:
        # Forza l'uso dell'italiano
        translation.activate('it')
        
        data = request.data
        logger.debug(f"Dati ricevuti per il salvataggio: {data}")
        
        # Controllo validità EAN/FNSKU: numerico, 12 o 13 cifre oppure alfanumerico, 10 caratteri
        ean = data.get('ean', '')
        if not (re.fullmatch(r'\d{12,13}', ean) or re.fullmatch(r'[A-Za-z0-9]{10}', ean)):
            return Response({
                "success": False,
                "messaggio": "Codice EAN/FNSKU non valido: deve essere una stringa numerica di 12 o 13 cifre o alfanumerica di 10 caratteri."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = PictureCheckSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "messaggio": f"EAN {data.get('ean')} salvato con successo.",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Errore nella validazione dei dati: {serializer.errors}")
            return Response({
                "success": False,
                "errori": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Errore nel salvataggio dell'EAN: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def lista_ean(request):
    """
    Ottiene la lista degli ultimi EAN verificati
    """
    try:
        # Forza l'uso dell'italiano
        translation.activate('it')
        
        # Recupera gli ultimi 50 EAN verificati ordinati per data più recente
        ean_list = PictureCheck.objects.all().order_by('-data')[:50]
        serializer = PictureCheckSerializer(ean_list, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Errore nel recupero della lista degli EAN: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
    

#@@@
from django.core.management import call_command
call_command('reset_ean_history.py')