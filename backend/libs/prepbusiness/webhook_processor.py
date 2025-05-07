"""
Module for processing webhook payloads from Prep Business.
This provides a clean interface for handling webhook data in various formats.
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from pydantic import ValidationError

from .models import WebhookPayload

logger = logging.getLogger('prep_management')

class WebhookProcessor:
    """
    Class for processing webhook payloads from Prep Business.
    Handles different formats and normalizes data for the application.
    """
    
    @classmethod
    def parse_payload(cls, payload_data: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parse and normalize webhook payload data.
        
        Args:
            payload_data: Raw webhook payload data (string, bytes or dict)
            
        Returns:
            Dict with normalized data for ShipmentStatusUpdate
        """
        # Convert payload to dict if it's a string or bytes
        if isinstance(payload_data, (str, bytes)):
            try:
                data = json.loads(payload_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse webhook payload JSON: {e}")
                raise ValueError("Invalid JSON payload")
        else:
            data = payload_data
            
        # Check if this is the new format with type/data structure
        if 'type' in data and 'data' in data:
            try:
                # Use the WebhookPayload model for parsing and validation
                webhook_payload = WebhookPayload(**data)
                return webhook_payload.to_shipment_update()
            except ValidationError as e:
                logger.warning(f"Webhook payload validation failed: {e}")
                # Fall back to manual extraction
                return cls._process_type_data_format(data)
        else:
            # Handle the old format (flat structure)
            return cls._process_flat_format(data)
    
    @staticmethod
    def _process_type_data_format(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process webhook payload in type/data format.
        
        Args:
            data: Webhook payload data with type and data fields
            
        Returns:
            Dict with extracted fields
        """
        event_type = data.get('type', 'other')
        payload_data = data.get('data', {})
        
        # Extract entity ID
        entity_id = str(payload_data.get('id', ''))
        
        # Extract entity type from event_type
        entity_type = event_type.split('.')[0] if '.' in event_type else ''
        
        # Extract status
        status = payload_data.get('status', 'other')
        
        # Map status to application format
        status_map = {
            'pending': 'pending',
            'processing': 'processing',
            'ready': 'ready',
            'shipped': 'shipped', 
            'delivered': 'delivered',
            'cancelled': 'cancelled',
            'failed': 'failed',
            'returned': 'returned',
            'created': 'created',
            'received': 'received',
            'notes_updated': 'notes_updated',
            'closed': 'closed',
            'open': 'pending',  # Map 'open' to 'pending'
            'draft': 'pending'  # Map 'draft' to 'pending'
        }
        
        mapped_status = status_map.get(status.lower(), 'other') if isinstance(status, str) else 'other'
        
        # Extract merchant information
        merchant_id = payload_data.get('team_id')
        merchant_name = None  # Don't set merchant_name here, it will be looked up later using merchant_id
            
        return {
            'shipment_id': entity_id,
            'event_type': event_type,
            'entity_type': entity_type,
            'new_status': mapped_status,
            'merchant_id': merchant_id,
            'merchant_name': merchant_name,
            'payload': data
        }
    
    @staticmethod
    def _process_flat_format(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process webhook payload in flat format.
        
        Args:
            data: Webhook payload data in flat format
            
        Returns:
            Dict with extracted fields
        """
        # Extract event type
        event_type = data.get('event_type', 'other')
        
        # If event_type is not specified, try to deduce it
        if event_type == 'other':
            action = data.get('action', '')
            entity_type = data.get('entity_type', '')
            
            if entity_type and action:
                event_type = f"{entity_type}.{action}"
        
        # Extract entity ID
        entity_id = str(data.get('id', '') or data.get('shipment_id', '') or 
                     data.get('order_id', '') or data.get('invoice_id', ''))
        
        # Determine entity type
        entity_type = data.get('entity_type', '')
        if not entity_type and '.' in event_type:
            entity_type = event_type.split('.')[0]
            
        # Extract status information
        new_status = data.get('status') or data.get('new_status') or 'other'
        previous_status = data.get('previous_status')
        
        # Map status to application format  
        status_map = {
            'pending': 'pending',
            'processing': 'processing',
            'ready': 'ready',
            'shipped': 'shipped',
            'delivered': 'delivered',
            'cancelled': 'cancelled',
            'failed': 'failed',
            'returned': 'returned',
            'created': 'created',
            'received': 'received',
            'notes_updated': 'notes_updated',
            'closed': 'closed'
        }
        
        mapped_status = status_map.get(new_status.lower(), 'other') if isinstance(new_status, str) else 'other'
        mapped_previous = status_map.get(previous_status.lower(), None) if isinstance(previous_status, str) else None
        
        # Extract additional information
        merchant_id = data.get('merchant_id') or data.get('merchant', {}).get('id')
        merchant_name = None  # Non impostiamo il merchant_name qui, verrà recuperato successivamente usando il merchant_id
        tracking_number = data.get('tracking_number') or data.get('tracking', {}).get('number')
        carrier = data.get('carrier') or data.get('tracking', {}).get('carrier')
        notes = data.get('notes') or data.get('message')
        
        return {
            'shipment_id': entity_id,
            'event_type': event_type,
            'entity_type': entity_type,
            'previous_status': mapped_previous,
            'new_status': mapped_status,
            'merchant_id': merchant_id,
            'merchant_name': merchant_name,
            'tracking_number': tracking_number,
            'carrier': carrier,
            'notes': notes,
            'payload': data
        } 