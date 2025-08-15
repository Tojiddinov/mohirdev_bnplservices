from django.utils import timezone
from datetime import timedelta
import json
import logging

from .models import IdempotencyKey

logger = logging.getLogger(__name__)


def check_idempotency(key):
    """
    Check if an idempotency key exists and is still valid
    Returns the cached response if found, None otherwise
    """
    try:
        idempotency_record = IdempotencyKey.objects.get(key=key)
        
        # Check if the key has expired
        if idempotency_record.expires_at < timezone.now():
            # Delete expired key
            idempotency_record.delete()
            return None
        
        logger.info(f"Found valid idempotency key: {key}")
        return idempotency_record.response_data
    
    except IdempotencyKey.DoesNotExist:
        return None


def save_idempotency_response(key, response_data, expiry_hours=24):
    """
    Save an idempotency key with its response
    Default expiry is 24 hours
    """
    try:
        IdempotencyKey.objects.create(
            key=key,
            response_data=response_data,
            expires_at=timezone.now() + timedelta(hours=expiry_hours)
        )
        logger.info(f"Saved idempotency key: {key}")
    except Exception as e:
        logger.error(f"Error saving idempotency key {key}: {str(e)}")


def clean_expired_idempotency_keys():
    """
    Clean up expired idempotency keys
    This can be called periodically via a Celery task
    """
    deleted_count = IdempotencyKey.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()[0]
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} expired idempotency keys")
    
    return deleted_count


def mask_sensitive_data(data):
    """
    Mask sensitive data in API responses
    """
    if isinstance(data, dict):
        masked_data = data.copy()
        
        # Mask card numbers
        if 'card_number' in masked_data:
            card = str(masked_data['card_number'])
            if len(card) >= 8:
                masked_data['card_number'] = f"{card[:4]} **** **** {card[-4:]}"
            else:
                masked_data['card_number'] = "**** **** **** ****"
        
        # Mask phone numbers
        if 'phone_number' in masked_data:
            phone = str(masked_data['phone_number'])
            if len(phone) > 7:
                masked_data['phone_number'] = f"+{phone[:3]}****{phone[-4:]}"
            else:
                masked_data['phone_number'] = "****"
        
        # Mask passport numbers
        if 'passport_number' in masked_data:
            masked_data['passport_number'] = "AA*******"
        
        # Mask personal info
        if 'personal_info' in masked_data:
            masked_data['personal_info'] = "***MASKED***"
        
        return masked_data
    
    return data
