#!/usr/bin/env python3
"""
Script per correggere gli errori di sintassi in event_handlers.py
"""

import re

def fix_event_handlers():
    file_path = 'prep_management/event_handlers.py'
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix 1: Correggi creation_type da "residuale" a "residual"
    content = content.replace('creation_type="residuale"', 'creation_type="residual"')
    
    # Fix 2: Correggi indentazioni nella funzione process_event
    lines = content.split('\n')
    fixed_lines = []
    in_process_event = False
    
    for i, line in enumerate(lines):
        if 'def process_event(self, update_id: int)' in line:
            in_process_event = True
            fixed_lines.append(line)
        elif in_process_event and line.strip().startswith('def ') and 'process_event' not in line:
            in_process_event = False
            fixed_lines.append(line)
        elif in_process_event:
            # Correggi indentazioni specifiche
            if 'update = ShipmentStatusUpdate.objects.get(id=update_id)' in line:
                fixed_lines.append('            update = ShipmentStatusUpdate.objects.get(id=update_id)')
            elif 'except ShipmentStatusUpdate.DoesNotExist:' in line:
                fixed_lines.append('        except ShipmentStatusUpdate.DoesNotExist:')
            elif 'return {\'success\': False, \'message\': f\'Update {update_id} non trovato.\'}' in line:
                fixed_lines.append('            return {\'success\': False, \'message\': f\'Update {update_id} non trovato.\'}')
            elif 'event_type = update.event_type' in line and line.strip().startswith('event_type'):
                fixed_lines.append('        event_type = update.event_type')
            elif 'update.processed = True' in line and line.strip().startswith('update.processed'):
                fixed_lines.append('        update.processed = True')
            elif 'update.process_success = result.get(\'success\', False)' in line:
                fixed_lines.append('        update.process_success = result.get(\'success\', False)')
            elif 'update.process_result = result' in line and line.strip().startswith('update.process_result'):
                fixed_lines.append('        update.process_result = result')
            elif 'update.processed_at = timezone.now()' in line:
                fixed_lines.append('        update.processed_at = timezone.now()')
            elif 'update.save()' in line and line.strip().startswith('update.save'):
                fixed_lines.append('        update.save()')
            elif 'return result' in line and line.strip().startswith('return result'):
                fixed_lines.append('        return result')
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Errori di sintassi corretti in event_handlers.py")

if __name__ == '__main__':
    fix_event_handlers() 