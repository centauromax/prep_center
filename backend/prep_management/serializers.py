from rest_framework import serializers
# Definisci qui i tuoi serializers.
from .models import OutgoingMessage

class OutgoingMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingMessage
        fields = ['id', 'message_id', 'parameters', 'created_at']
