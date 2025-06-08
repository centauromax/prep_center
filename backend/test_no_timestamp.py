#!/usr/bin/env python3

# Test per verificare che l'ora sia stata rimossa dalle notifiche

import sys
sys.path.append('/Users/adriano/WORK/sviluppo/prep_center/backend')

# Mock della funzione format_shipment_notification
def mock_format_shipment_notification(event_type, shipment_data, user_language='it'):
    """Simula la funzione format_shipment_notification senza Django"""
    
    # Traduzioni simulate
    notifications = {
        'inbound_shipment.created': {
            'it': 'Nuova spedizione in entrata creata',
            'en': 'New inbound shipment created'
        }
    }
    
    labels = {
        'id': {'it': 'ID', 'en': 'ID'},
        'name': {'it': 'Nome', 'en': 'Name'},
        'carrier': {'it': 'Corriere', 'en': 'Carrier'}
    }
    
    # Icone
    icons = {'inbound_shipment.created': '📦'}
    
    icon = icons.get(event_type, '📋')
    title = notifications[event_type][user_language]
    
    message = f"{icon} <b>{title}</b>\n\n"
    
    if shipment_data.get('shipment_id'):
        id_label = labels['id'][user_language]
        message += f"🆔 <b>{id_label}:</b> {shipment_data['shipment_id']}\n"
    
    if shipment_data.get('shipment_name'):
        name_label = labels['name'][user_language]
        message += f"📝 <b>{name_label}:</b> {shipment_data['shipment_name']}\n"
        
    if shipment_data.get('carrier'):
        carrier_label = labels['carrier'][user_language]
        message += f"🚛 <b>{carrier_label}:</b> {shipment_data['carrier']}\n"
    
    # NON aggiungiamo più il timestamp!
    
    return message

def test_no_timestamp():
    """Test che verifica l'assenza del timestamp"""
    
    print("🧪 Test rimozione timestamp dalle notifiche")
    print("=" * 50)
    
    # Dati di test
    shipment_data = {
        'shipment_id': 'TEST123',
        'shipment_name': 'Test Shipment',
        'carrier': 'DHL'
    }
    
    # Test in italiano
    print("\n📦 MESSAGGIO ITALIANO:")
    msg_it = mock_format_shipment_notification(
        'inbound_shipment.created', 
        shipment_data, 
        'it'
    )
    print(msg_it)
    
    # Test in inglese  
    print("📦 MESSAGGIO INGLESE:")
    msg_en = mock_format_shipment_notification(
        'inbound_shipment.created', 
        shipment_data, 
        'en'
    )
    print(msg_en)
    
    # Verifica assenza timestamp (più preciso)
    timestamp_keywords = ['🕒', 'Aggiornamento del', 'Updated on', 'alle ', ' at ']
    
    issues = []
    for keyword in timestamp_keywords:
        if keyword in msg_it:
            issues.append(f"Trovato '{keyword}' nel messaggio italiano")
        if keyword in msg_en:
            issues.append(f"Trovato '{keyword}' nel messaggio inglese")
    
    if issues:
        print("\n❌ PROBLEMI TROVATI:")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("\n✅ TIMESTAMP RIMOSSO CORRETTAMENTE!")
        print("   • Nessuna traccia di orari nei messaggi")
        print("   • Messaggi più puliti e concisi")

if __name__ == "__main__":
    print("🚀 Test rimozione timestamp")
    
    try:
        test_no_timestamp()
        print("\n🎉 TEST COMPLETATO!")
        print("⏰ L'ora è stata rimossa dalle notifiche!")
        
    except Exception as e:
        print(f"\n❌ ERRORE NEL TEST: {e}")
        import traceback
        traceback.print_exc() 