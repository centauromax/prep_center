#!/bin/bash

echo "🧪 TEST: Verifica fix logica residuale"
echo "Aspetto deploy e poi testo webhook outbound.closed..."
echo ""

# Aspetta che il deploy sia completato
counter=1
max_attempts=15

while [ $counter -le $max_attempts ]; do
    echo "[$counter/$max_attempts] Controllo deploy $(date '+%H:%M:%S')..."
    
    response=$(curl -s -o /dev/null -w "%{http_code}" https://backend.fbaprepcenteritaly.com/prep_management/debug/webhook-processor/)
    
    if [ "$response" = "200" ]; then
        echo "✅ Deploy completato!"
        break
    fi
    
    if [ $counter -eq $max_attempts ]; then
        echo "💥 TIMEOUT deploy!"
        exit 1
    fi
    
    sleep 8
    counter=$((counter + 1))
done

echo ""
echo "🚀 INVIO WEBHOOK TEST OUTBOUND.CLOSED..."

# Webhook di test con formato che dovrebbe funzionare ora
webhook_response=$(curl -s -X POST https://backend.fbaprepcenteritaly.com/prep_management/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "id": 643084,
    "name": "TEST-RESIDUAL-FIX",
    "status": "closed",
    "team_id": 7812,
    "tracking_number": "TEST123456",
    "carrier": "DHL",
    "notes": "Test webhook per verifica fix logica residuale",
    "shipped_at": "2024-01-15T10:30:00Z",
    "warehouse_id": 1,
    "outbound_items": [
      {
        "id": 1001,
        "product_id": 501,
        "sku": "TEST-SKU-001",
        "quantity": 5,
        "name": "Prodotto Test 1"
      },
      {
        "id": 1002,
        "product_id": 502,
        "sku": "TEST-SKU-002", 
        "quantity": 3,
        "name": "Prodotto Test 2"
      }
    ]
  }')

echo "📨 Webhook inviato!"
echo "📋 Risposta: $webhook_response"
echo ""

# Aspetta un po' per il processing
echo "⏳ Aspetto 5 secondi per processing..."
sleep 5

echo ""
echo "🔍 CONTROLLO RISULTATI:"

# Controlla lo stato del processor
debug_data=$(curl -s https://backend.fbaprepcenteritaly.com/prep_management/debug/webhook-processor/)

# Estrai info chiave
unprocessed_events=$(echo "$debug_data" | jq -r '.debug_info.unprocessed_events // "unknown"')
outbound_closed_count=$(echo "$debug_data" | jq -r '.debug_info.outbound_closed_count // "unknown"')

echo "⏳ Eventi non processati: $unprocessed_events"
echo "📦 Eventi outbound.closed totali: $outbound_closed_count"

echo ""
echo "📋 ULTIMI 3 EVENTI OUTBOUND.CLOSED:"
echo "$debug_data" | jq -r '.recent_outbound_closed_events[0:3][] | "ID: \(.id) | Shipment: \(.shipment_id) | Processato: \(.processed) | Successo: \(.process_success) | Messaggio: \(.process_message // "nessuno")"'

# Cerca specificamente il nostro test
echo ""
echo "🎯 CERCA IL NOSTRO TEST (Shipment 643084):"
our_test=$(echo "$debug_data" | jq -r '.recent_outbound_closed_events[] | select(.shipment_id == "643084") | "ID: \(.id) | Processato: \(.processed) | Successo: \(.process_success) | Messaggio: \(.process_message // "nessuno")"')

if [ -n "$our_test" ]; then
    echo "✅ TROVATO: $our_test"
    
    # Controlla se è stato processato con successo
    success=$(echo "$debug_data" | jq -r '.recent_outbound_closed_events[] | select(.shipment_id == "643084") | .process_success')
    
    if [ "$success" = "true" ]; then
        echo "🎉 SUCCESS! La logica residuale ha funzionato!"
    else
        echo "❌ FALLITO: La logica residuale non ha funzionato"
        echo "🔍 Messaggio errore:"
        echo "$debug_data" | jq -r '.recent_outbound_closed_events[] | select(.shipment_id == "643084") | .process_message // "nessun messaggio"'
    fi
else
    echo "❌ NON TROVATO: Il nostro test non è presente negli eventi recenti"
fi

echo ""
echo "🏁 Test completato!" 