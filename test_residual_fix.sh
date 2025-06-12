#!/bin/bash

echo "🔧 TEST: Correzione logica residuale inbound"
echo "Aspettando deploy Railway..."
echo ""

# Aspetta che il deploy sia completato
counter=1
max_attempts=15

while [ $counter -le $max_attempts ]; do
    echo "[$counter/$max_attempts] Controllo deploy $(date '+%H:%M:%S')..."
    
    response=$(curl -s -o /dev/null -w "%{http_code}" https://backend.fbaprepcenteritaly.com/prep_management/webhook/)
    
    if [ "$response" = "405" ]; then
        echo "✅ Deploy completato!"
        break
    fi
    
    if [ $counter -eq $max_attempts ]; then
        echo "💥 TIMEOUT deploy"
        exit 1
    fi
    
    sleep 10
    counter=$((counter + 1))
done

echo ""
echo "🧪 TEST: Webhook outbound_shipment.closed che dovrebbe creare inbound residuale"

test_response=$(curl -s -X POST https://backend.fbaprepcenteritaly.com/prep_management/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "id": 555777,
    "name": "test-residual-creation",
    "status": "closed",
    "shipped_at": "2025-06-12T17:00:00.000000Z",
    "team_id": 7812,
    "warehouse_id": 310,
    "notes": "Test creazione inbound residuale dopo fix client"
  }')

echo "Risposta webhook: $test_response"

# Estrai update_id
update_id=$(echo "$test_response" | grep -o '"update_id":[0-9]*' | cut -d':' -f2)
echo "Update ID: $update_id"

# Estrai event_type
event_type=$(echo "$test_response" | grep -o '"event_type":"[^"]*"' | cut -d'"' -f4)
echo "Event Type: $event_type"

if [ "$event_type" = "outbound_shipment.closed" ]; then
    echo "✅ Event type corretto: outbound_shipment.closed"
    echo ""
    echo "🔍 Ora controlla i log Railway per vedere se:"
    echo "   1. WebhookEventProcessor client si inizializza correttamente"
    echo "   2. _process_outbound_shipment_closed viene chiamato"
    echo "   3. Viene creato un inbound residuale"
    echo ""
    echo "📋 Comandi per controllare:"
    echo "   railway logs -s prep_center_backend | grep -E \"(update_id: $update_id|_process_outbound_shipment_closed|Client.*inizializzato)\""
else
    echo "❌ Event type errato: $event_type (atteso: outbound_shipment.closed)"
fi

echo ""
echo "🎯 PROSSIMI PASSI:"
echo "1. Controlla i log per verificare l'inizializzazione del client"
echo "2. Verifica se viene chiamato _process_outbound_shipment_closed"
echo "3. Controlla se viene creato un nuovo inbound shipment" 