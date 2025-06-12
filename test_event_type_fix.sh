#!/bin/bash

echo "🔧 TEST: Correzione riconoscimento tipo evento"
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
echo "🧪 TEST 1: Webhook con status=closed + shipped_at + warehouse_id (dovrebbe essere OUTBOUND)"

test1_response=$(curl -s -X POST https://backend.fbaprepcenteritaly.com/prep_management/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "id": 777001,
    "name": "test-outbound-recognition",
    "status": "closed",
    "shipped_at": "2025-06-12T16:00:00.000000Z",
    "team_id": 7812,
    "warehouse_id": 310,
    "notes": "Test riconoscimento outbound"
  }')

echo "Risposta Test 1: $test1_response"

# Estrai event_type dalla risposta
event_type1=$(echo "$test1_response" | grep -o '"event_type":"[^"]*"' | cut -d'"' -f4)
echo "Event Type riconosciuto: $event_type1"

if [ "$event_type1" = "outbound_shipment.closed" ]; then
    echo "✅ TEST 1 SUCCESSO: Riconosciuto correttamente come outbound_shipment.closed"
else
    echo "❌ TEST 1 FALLITO: Atteso outbound_shipment.closed, ottenuto $event_type1"
fi

echo ""
echo "🧪 TEST 2: Webhook senza warehouse_id e status=open (dovrebbe essere INBOUND)"

test2_response=$(curl -s -X POST https://backend.fbaprepcenteritaly.com/prep_management/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "id": 777002,
    "name": "test-inbound-recognition",
    "status": "open",
    "team_id": 7812,
    "notes": "Test riconoscimento inbound"
  }')

echo "Risposta Test 2: $test2_response"

event_type2=$(echo "$test2_response" | grep -o '"event_type":"[^"]*"' | cut -d'"' -f4)
echo "Event Type riconosciuto: $event_type2"

if [ "$event_type2" = "inbound_shipment.created" ]; then
    echo "✅ TEST 2 SUCCESSO: Riconosciuto correttamente come inbound_shipment.created"
else
    echo "❌ TEST 2 FALLITO: Atteso inbound_shipment.created, ottenuto $event_type2"
fi

echo ""
echo "🎯 RISULTATO FINALE:"
if [ "$event_type1" = "outbound_shipment.closed" ] && [ "$event_type2" = "inbound_shipment.created" ]; then
    echo "🎉 TUTTI I TEST PASSATI! Riconoscimento tipo evento CORRETTO"
else
    echo "⚠️  Alcuni test falliti - controllare i log"
fi 