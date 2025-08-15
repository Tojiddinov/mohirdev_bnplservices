from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from .models import Installment, User, InstallmentStatus, UserStatus
from .utils import clean_expired_idempotency_keys

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_payments():
    """
    Celery task to check for overdue payments and update user statuses
    This runs every 5 minutes via Celery Beat
    """
    try:
        with transaction.atomic():
            # Find all overdue installments
            overdue_installments = Installment.objects.filter(
                status=InstallmentStatus.UPCOMING,
                due_date__lt=timezone.now().date()
            ).select_related('plan__user')
            
            if not overdue_installments.exists():
                logger.info("No overdue installments found")
                return
            
            # Group by user for efficient processing
            users_to_update = set()
            updated_installments = 0
            
            for installment in overdue_installments:
                # Mark installment as overdue
                installment.status = InstallmentStatus.OVERDUE
                installment.save()
                updated_installments += 1
                
                # Mark user for status update
                users_to_update.add(installment.plan.user)
            
            # Update user statuses to DEBT_USER
            for user in users_to_update:
                if user.status != UserStatus.DEBT_USER:
                    user.status = UserStatus.DEBT_USER
                    user.save()
                    logger.info(f"User {user.user_id} status changed to DEBT_USER")
            
            logger.info(f"Processed {updated_installments} overdue installments for {len(users_to_update)} users")
            
    except Exception as e:
        logger.error(f"Error in check_overdue_payments task: {str(e)}")
        raise


@shared_task
def clean_expired_idempotency_keys():
    """
    Celery task to clean up expired idempotency keys
    This runs every hour via Celery Beat
    """
    try:
        deleted_count = clean_expired_idempotency_keys()
        logger.info(f"Cleaned up {deleted_count} expired idempotency keys")
        return deleted_count
    except Exception as e:
        logger.error(f"Error in clean_expired_idempotency_keys task: {str(e)}")
        raise


@shared_task
def process_refund_webhook(refund_id, status, merchant_reference=None):
    """
    Celery task to process refund webhook from merchant
    This can be called when merchant approves/rejects a refund
    """
    try:
        from .models import Refund, RefundStatus
        
        refund = Refund.objects.get(id=refund_id)
        
        if status == 'approved':
            refund.status = RefundStatus.APPROVED
            refund.processed_at = timezone.now()
            logger.info(f"Refund {refund_id} approved via webhook")
        elif status == 'rejected':
            refund.status = RefundStatus.REJECTED
            refund.reason = f"Rejected via webhook: {merchant_reference or 'No reference'}"
            refund.processed_at = timezone.now()
            logger.info(f"Refund {refund_id} rejected via webhook")
        
        refund.save()
        return f"Refund {refund_id} processed successfully"
        
    except Refund.DoesNotExist:
        logger.error(f"Refund {refund_id} not found for webhook processing")
        raise
    except Exception as e:
        logger.error(f"Error processing refund webhook for {refund_id}: {str(e)}")
        raise
