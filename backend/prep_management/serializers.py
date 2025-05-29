from rest_framework import serializers
# Definisci qui i tuoi serializers.
from .models import OutgoingMessage, IncomingMessage

class OutgoingMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingMessage
        fields = ['id', 'message_id', 'parameters', 'created_at']

class IncomingMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomingMessage
        fields = ['id', 'message_type', 'payload', 'session_id', 'created_at', 'processed']
