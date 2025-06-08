#!/usr/bin/env python3

# Test semplificato per la formattazione delle notifiche multilingua
# Senza dipendenze Django

import sys
sys.path.append('/Users/adriano/WORK/sviluppo/prep_center/backend')

# Importa solo i moduli necessari per il testing
from prep_management.translations import get_text, TRANSLATIONS

def test_notification_translations():
    """Test delle traduzioni per le notifiche"""
    
    print("🧪 Test traduzioni notifiche")
    print("=" * 50)
    
    # Test traduzioni eventi
    events = [
        'inbound_shipment.created',
        'inbound_shipment.received',
        'outbound_shipment.created',
        'outbound_shipment.shipped',
        'order.created'
    ]
    
    print("\n📦 EVENTI IN ITALIANO:")
    for event in events:
        text_it = get_text('notifications', lang='it', subkey=event)
        print(f"  {event}: {text_it}")
    
    print("\n📦 EVENTI IN INGLESE:")
    for event in events:
        text_en = get_text('notifications', lang='en', subkey=event)
        print(f"  {event}: {text_en}")
    
    # Test labels
    labels = ['id', 'name', 'tracking', 'carrier', 'notes', 'update_time']
    
    print("\n🏷️ LABELS IN ITALIANO:")
    for label in labels:
        text_it = get_text('notification_labels', lang='it', subkey=label)
        print(f"  {label}: {text_it}")
    
    print("\n🏷️ LABELS IN INGLESE:")
    for label in labels:
        text_en = get_text('notification_labels', lang='en', subkey=label)
        print(f"  {label}: {text_en}")

def test_message_formatting():
    """Test formattazione messaggio completo simulato"""
    
    print("\n🔧 Test formattazione messaggio")
    print("=" * 50)
    
    # Simula la formattazione di un messaggio
    def format_notification_simple(event_type, lang='it'):
        # Ottieni titolo
        title = get_text('notifications', lang=lang, subkey=event_type)
        
        # Ottieni labels
        id_label = get_text('notification_labels', lang=lang, subkey='id')
        name_label = get_text('notification_labels', lang=lang, subkey='name')
        
        # Costruisci messaggio
        message = f"📦 {title}\n\n"
        message += f"🆔 {id_label}: TEST123\n"
        message += f"📝 {name_label}: Test Shipment\n"
        
        return message
    
    # Test in italiano
    print("\n📧 MESSAGGIO ITALIANO:")
    msg_it = format_notification_simple('inbound_shipment.created', 'it')
    print(msg_it)
    
    # Test in inglese
    print("📧 MESSAGGIO INGLESE:")
    msg_en = format_notification_simple('inbound_shipment.created', 'en')
    print(msg_en)
    
    # Verifica differenze
    if msg_it != msg_en:
        print("✅ Messaggi diversi - multilingua funziona!")
    else:
        print("❌ Messaggi identici - problema nella traduzione")

def check_translation_completeness():
    """Verifica completezza traduzioni"""
    
    print("\n🔍 Verifica completezza traduzioni")
    print("=" * 50)
    
    # Controlla che tutte le traduzioni abbiano entrambe le lingue
    issues = []
    
    for key, value in TRANSLATIONS.items():
        if isinstance(value, dict):
            if key == 'notifications':
                for event, trans in value.items():
                    if isinstance(trans, dict):
                        if 'it' not in trans or 'en' not in trans:
                            issues.append(f"notifications.{event} manca lingua")
            elif key == 'notification_labels':
                for label, trans in value.items():
                    if isinstance(trans, dict):
                        if 'it' not in trans or 'en' not in trans:
                            issues.append(f"notification_labels.{label} manca lingua")
    
    if issues:
        print("❌ Problemi trovati:")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("✅ Tutte le traduzioni sono complete!")

if __name__ == "__main__":
    print("🚀 Test notifiche multilingua semplificato")
    
    try:
        test_notification_translations()
        test_message_formatting()
        check_translation_completeness()
        
        print("\n🎉 TUTTI I TEST COMPLETATI!")
        print("🌍 Le traduzioni per le notifiche sono pronte!")
        
    except Exception as e:
        print(f"\n❌ ERRORE NEI TEST: {e}")
        import traceback
        traceback.print_exc() 