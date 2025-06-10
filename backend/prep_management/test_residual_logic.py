"""
Test script per verificare la logica di calcolo residual senza dipendenze Django.
"""

def calculate_residual_items(inbound_items, outbound_items):
    """
    Versione semplificata della logica di calcolo residual per test.
    """
    print(f"[TEST] Calcolo residual da {len(inbound_items)} inbound e {len(outbound_items)} outbound items")
    
    # Crea un mapping dei prodotti outbound per item_id
    outbound_quantities = {}
    for item in outbound_items:
        item_id = item.get('item_id')
        quantity_shipped = item.get('quantity', 0)
        outbound_quantities[item_id] = outbound_quantities.get(item_id, 0) + quantity_shipped
        print(f"[TEST] Outbound - Item ID {item_id}: {quantity_shipped} shipped")
    
    residual_items = []
    
    for inbound_item in inbound_items:
        item_id = inbound_item.get('item_id')
        expected_qty = inbound_item.get('expected_quantity', 0)
        actual_qty = inbound_item.get('actual_quantity', 0)
        shipped_qty = outbound_quantities.get(item_id, 0)
        
        # Calcola le quantità residuali
        residual_expected = max(0, expected_qty - shipped_qty)
        residual_actual = max(0, actual_qty - shipped_qty)
        
        print(f"[TEST] Item ID {item_id}: Expected {expected_qty} - Shipped {shipped_qty} = Residual Expected {residual_expected}")
        print(f"[TEST] Item ID {item_id}: Actual {actual_qty} - Shipped {shipped_qty} = Residual Actual {residual_actual}")
        
        # Includi solo se almeno una delle quantità è > 0
        if residual_expected > 0 or residual_actual > 0:
            residual_item = {
                'item_id': item_id,
                'title': inbound_item.get('title', ''),
                'expected_quantity': residual_expected,
                'actual_quantity': residual_actual
            }
            residual_items.append(residual_item)
            print(f"[TEST] ✅ Aggiunto residual: {residual_item}")
        else:
            print(f"[TEST] ❌ Item ID {item_id} - nessun residual (entrambe le quantità = 0)")
    
    print(f"[TEST] ✅ Calcolati {len(residual_items)} prodotti residuali")
    return residual_items

def test_scenario_from_user():
    """
    Test dello scenario fornito dall'utente.
    """
    print("\n" + "="*80)
    print("TEST SCENARIO UTENTE")
    print("="*80)
    
    # Inbound originale
    inbound_items = [
        {'item_id': 1, 'title': 'Prodotto1', 'expected_quantity': 10, 'actual_quantity': 10},
        {'item_id': 2, 'title': 'Prodotto2', 'expected_quantity': 5, 'actual_quantity': 5},
        {'item_id': 3, 'title': 'Prodotto3', 'expected_quantity': 3, 'actual_quantity': 3},
        {'item_id': 4, 'title': 'Prodotto4', 'expected_quantity': 8, 'actual_quantity': 0},
        {'item_id': 5, 'title': 'Prodotto5', 'expected_quantity': 5, 'actual_quantity': 4},
        {'item_id': 6, 'title': 'Prodotto6', 'expected_quantity': 20, 'actual_quantity': 21},
    ]
    
    # Outbound completato
    outbound_items = [
        {'item_id': 1, 'quantity': 5},
        {'item_id': 2, 'quantity': 5},
        {'item_id': 3, 'quantity': 2},
        {'item_id': 4, 'quantity': 0},
        {'item_id': 5, 'quantity': 4},
        {'item_id': 6, 'quantity': 15},
    ]
    
    print("\nINBOUND ORIGINALE:")
    for item in inbound_items:
        print(f"  {item['title']}: Expected {item['expected_quantity']}, Actual {item['actual_quantity']}")
    
    print("\nOUTBOUND COMPLETATO:")
    for item in outbound_items:
        title = next((i['title'] for i in inbound_items if i['item_id'] == item['item_id']), f"Item{item['item_id']}")
        print(f"  {title}: Shipped {item['quantity']}")
    
    print("\nCALCOLO RESIDUAL:")
    residual_items = calculate_residual_items(inbound_items, outbound_items)
    
    print("\nRESIDUAL ATTESO:")
    expected_residual = [
        {'item_id': 1, 'title': 'Prodotto1', 'expected_quantity': 5, 'actual_quantity': 5},
        {'item_id': 3, 'title': 'Prodotto3', 'expected_quantity': 1, 'actual_quantity': 1},
        {'item_id': 4, 'title': 'Prodotto4', 'expected_quantity': 8, 'actual_quantity': 0},
        {'item_id': 5, 'title': 'Prodotto5', 'expected_quantity': 1, 'actual_quantity': 0},
        {'item_id': 6, 'title': 'Prodotto6', 'expected_quantity': 5, 'actual_quantity': 6},
    ]
    
    print("  Expected residual:")
    for item in expected_residual:
        print(f"    {item['title']}: Expected {item['expected_quantity']}, Actual {item['actual_quantity']}")
    
    print("\nRESIDUAL CALCOLATO:")
    for item in residual_items:
        print(f"    {item['title']}: Expected {item['expected_quantity']}, Actual {item['actual_quantity']}")
    
    # Verifica che il risultato sia corretto
    success = True
    if len(residual_items) != len(expected_residual):
        print(f"❌ ERRORE: Numero items diverso - Atteso: {len(expected_residual)}, Calcolato: {len(residual_items)}")
        success = False
    
    for expected in expected_residual:
        found = next((r for r in residual_items if r['item_id'] == expected['item_id']), None)
        if not found:
            print(f"❌ ERRORE: Item {expected['item_id']} mancante nel residual")
            success = False
        elif (found['expected_quantity'] != expected['expected_quantity'] or 
              found['actual_quantity'] != expected['actual_quantity']):
            print(f"❌ ERRORE: Item {expected['item_id']} - Quantità diverse")
            print(f"   Atteso: Expected {expected['expected_quantity']}, Actual {expected['actual_quantity']}")
            print(f"   Calcolato: Expected {found['expected_quantity']}, Actual {found['actual_quantity']}")
            success = False
    
    if success:
        print("\n✅ TEST SUPERATO: Logica di calcolo residual corretta!")
    else:
        print("\n❌ TEST FALLITO: Errori nella logica di calcolo residual")
    
    return success

def test_edge_cases():
    """
    Test di casi limite.
    """
    print("\n" + "="*80)
    print("TEST CASI LIMITE")
    print("="*80)
    
    # Caso 1: Outbound non spedisce nulla
    print("\nCASO 1: Outbound non spedisce nulla")
    inbound = [{'item_id': 1, 'title': 'Test', 'expected_quantity': 10, 'actual_quantity': 8}]
    outbound = []
    residual = calculate_residual_items(inbound, outbound)
    print(f"  Risultato: {residual}")
    assert len(residual) == 1 and residual[0]['expected_quantity'] == 10 and residual[0]['actual_quantity'] == 8
    print("  ✅ OK")
    
    # Caso 2: Tutto spedito esattamente
    print("\nCASO 2: Tutto spedito esattamente")
    inbound = [{'item_id': 1, 'title': 'Test', 'expected_quantity': 10, 'actual_quantity': 10}]
    outbound = [{'item_id': 1, 'quantity': 10}]
    residual = calculate_residual_items(inbound, outbound)
    print(f"  Risultato: {residual}")
    assert len(residual) == 0
    print("  ✅ OK")
    
    # Caso 3: Spedito più del previsto (non dovrebbe mai succedere, ma gestiamo)
    print("\nCASO 3: Spedito più del previsto")
    inbound = [{'item_id': 1, 'title': 'Test', 'expected_quantity': 10, 'actual_quantity': 8}]
    outbound = [{'item_id': 1, 'quantity': 15}]
    residual = calculate_residual_items(inbound, outbound)
    print(f"  Risultato: {residual}")
    assert len(residual) == 0  # Entrambe le quantità diventano 0 (max(0, ...))
    print("  ✅ OK")
    
    # Caso 4: Prodotti nell'outbound che non esistono nell'inbound
    print("\nCASO 4: Prodotti nell'outbound che non esistono nell'inbound")
    inbound = [{'item_id': 1, 'title': 'Test1', 'expected_quantity': 10, 'actual_quantity': 10}]
    outbound = [
        {'item_id': 1, 'quantity': 5},
        {'item_id': 999, 'quantity': 3}  # Questo non dovrebbe influenzare il calcolo
    ]
    residual = calculate_residual_items(inbound, outbound)
    print(f"  Risultato: {residual}")
    assert len(residual) == 1 and residual[0]['expected_quantity'] == 5 and residual[0]['actual_quantity'] == 5
    print("  ✅ OK")
    
    print("\n✅ TUTTI I CASI LIMITE SUPERATI!")

if __name__ == "__main__":
    success1 = test_scenario_from_user()
    test_edge_cases()
    
    if success1:
        print("\n🎉 TUTTI I TEST SUPERATI! La logica è pronta per l'implementazione.")
    else:
        print("\n❌ Alcuni test falliti. Rivedere la logica prima del deploy.") 