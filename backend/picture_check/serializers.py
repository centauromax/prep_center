from rest_framework import serializers
from .models import PictureCheck, Cliente

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['id', 'nome', 'attivo']

class PictureCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = PictureCheck
        fields = ['id', 'data', 'ean', 'cliente']
        read_only_fields = ['data'] 