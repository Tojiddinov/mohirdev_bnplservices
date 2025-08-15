from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta, date
import uuid
import logging
import json
import hashlib

from .models import (
    User, BNPLPlan, Installment, Refund, 
    IdempotencyKey, UserStatus, RefundStatus, InstallmentStatus
)
from .serializers import (
    MaskedUserSerializer, BNPLPlanSerializer, CreateBNPLPlanSerializer,
    RefundSerializer, CreateRefundSerializer, RefundApprovalSerializer,
    DebtCheckSerializer, RepaymentSerializer, InstallmentSerializer
)
from .utils import check_idempotency, save_idempotency_response

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for User operations"""
    queryset = User.objects.all()
    serializer_class = MaskedUserSerializer
    lookup_field = 'user_id'
    
    def list(self, request, *args, **kwargs):
        """List all users with masked information"""
        logger.info("Fetching all users")
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Get specific user with masked information"""
        user_id = kwargs.get('user_id')
        logger.info(f"Fetching user: {user_id}")
        return super().retrieve(request, *args, **kwargs)


class BNPLPlanViewSet(viewsets.ModelViewSet):
    """ViewSet for BNPL Plan operations"""
    queryset = BNPLPlan.objects.all()
    serializer_class = BNPLPlanSerializer
    
    def get_queryset(self):
        """Filter plans by user if user_id is provided"""
        queryset = super().get_queryset()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset.select_related('user').prefetch_related('installments')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new BNPL plan"""
        # Check for idempotency
        idempotency_key = request.headers.get('X-Idempotency-Key')
        if idempotency_key:
            cached_response = check_idempotency(idempotency_key)
            if cached_response:
                return Response(cached_response, status=status.HTTP_200_OK)
        
        serializer = CreateBNPLPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_id = serializer.validated_data['user_id']
        total_amount = serializer.validated_data['total_amount']
        installment_count = serializer.validated_data.get('installment_count', 3)
        
        # Get user and check status
        user = get_object_or_404(User, user_id=user_id)
        if user.status == UserStatus.DEBT_USER:
            logger.warning(f"User {user_id} with DEBT_USER status attempted to create plan")
            return Response(
                {"error": "Users with DEBT_USER status cannot create new BNPL plans"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create BNPL Plan
        plan = BNPLPlan.objects.create(
            user=user,
            total_amount=total_amount,
            status='ACTIVE'
        )
        
        # Create installments
        installment_amount = total_amount / installment_count
        current_date = date.today()
        
        for i in range(installment_count):
            due_date = current_date + timedelta(days=30 * (i + 1))
            Installment.objects.create(
                plan=plan,
                amount_due=installment_amount,
                due_date=due_date,
                status=InstallmentStatus.UPCOMING
            )
        
        response_data = BNPLPlanSerializer(plan).data
        
        # Save idempotency response
        if idempotency_key:
            save_idempotency_response(idempotency_key, response_data)
        
        logger.info(f"Created BNPL plan {plan.id} for user {user_id}")
        return Response(response_data, status=status.HTTP_201_CREATED)


class DebtManagementView(APIView):
    """View for debt management operations"""
    
    def get(self, request, user_id):
        """Check user's debt status"""
        user = get_object_or_404(User, user_id=user_id)
        
        # Get all overdue installments for the user
        overdue_installments = Installment.objects.filter(
            plan__user=user,
            status=InstallmentStatus.OVERDUE
        ).select_related('plan')
        
        # Calculate total debt
        total_debt = sum(inst.amount_due for inst in overdue_installments)
        
        response_data = {
            "user_id": user_id,
            "has_overdue": overdue_installments.exists(),
            "total_debt": str(total_debt),
            "overdue_installments": InstallmentSerializer(overdue_installments, many=True).data,
            "user_status": user.status
        }
        
        logger.info(f"Debt check for user {user_id}: has_overdue={overdue_installments.exists()}, total_debt={total_debt}")
        return Response(response_data, status=status.HTTP_200_OK)
    
    @transaction.atomic
    def post(self, request, user_id):
        """Process repayment for overdue installments"""
        # Check for idempotency
        idempotency_key = request.headers.get('X-Idempotency-Key')
        if idempotency_key:
            cached_response = check_idempotency(idempotency_key)
            if cached_response:
                return Response(cached_response, status=status.HTTP_200_OK)
        
        user = get_object_or_404(User, user_id=user_id)
        serializer = RepaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        installment_ids = serializer.validated_data['installment_ids']
        
        # Update installments to PAID
        installments = Installment.objects.filter(
            id__in=installment_ids,
            plan__user=user,
            status=InstallmentStatus.OVERDUE
        )
        
        if installments.count() != len(installment_ids):
            return Response(
                {"error": "Some installments are invalid or not overdue"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark installments as paid
        installments.update(
            status=InstallmentStatus.PAID,
            paid_at=timezone.now()
        )
        
        # Check if user has any remaining overdue installments
        remaining_overdue = Installment.objects.filter(
            plan__user=user,
            status=InstallmentStatus.OVERDUE
        ).exists()
        
        # Update user status if no more overdue installments
        if not remaining_overdue and user.status == UserStatus.DEBT_USER:
            user.status = UserStatus.NORMAL
            user.save()
            logger.info(f"User {user_id} status changed back to NORMAL")
        
        response_data = {
            "message": "Repayment processed successfully",
            "paid_installments": len(installment_ids),
            "user_status": user.status
        }
        
        # Save idempotency response
        if idempotency_key:
            save_idempotency_response(idempotency_key, response_data)
        
        logger.info(f"Processed repayment for user {user_id}: {len(installment_ids)} installments paid")
        return Response(response_data, status=status.HTTP_200_OK)


class RefundViewSet(viewsets.ModelViewSet):
    """ViewSet for Refund operations"""
    queryset = Refund.objects.all()
    serializer_class = RefundSerializer
    
    def get_queryset(self):
        """Filter refunds by user if user_id is provided"""
        queryset = super().get_queryset()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset.select_related('user')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new refund request"""
        # Check for idempotency using transaction_id
        transaction_id = request.data.get('transaction_id')
        if transaction_id:
            existing_refund = Refund.objects.filter(transaction_id=transaction_id).first()
            if existing_refund:
                logger.info(f"Idempotent request for transaction_id: {transaction_id}")
                return Response(
                    RefundSerializer(existing_refund).data,
                    status=status.HTTP_200_OK
                )
        
        serializer = CreateRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = get_object_or_404(User, user_id=serializer.validated_data['user_id'])
        
        refund = Refund.objects.create(
            user=user,
            transaction_id=serializer.validated_data['transaction_id'],
            amount=serializer.validated_data['amount'],
            reason=serializer.validated_data.get('reason', ''),
            status=RefundStatus.PENDING
        )
        
        logger.info(f"Created refund request {refund.id} for user {user.user_id}")
        return Response(
            RefundSerializer(refund).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], url_path='approve')
    @transaction.atomic
    def approve_refund(self, request, pk=None):
        """Approve or reject a refund request"""
        refund = self.get_object()
        
        if refund.status != RefundStatus.PENDING:
            return Response(
                {"error": f"Cannot process refund with status {refund.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = RefundApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')
        
        if action == 'approve':
            refund.status = RefundStatus.APPROVED
            refund.processed_at = timezone.now()
            logger.info(f"Refund {refund.id} approved")
        else:
            refund.status = RefundStatus.REJECTED
            refund.reason = f"Rejected: {reason}" if reason else "Rejected"
            refund.processed_at = timezone.now()
            logger.info(f"Refund {refund.id} rejected")
        
        refund.save()
        
        return Response(
            RefundSerializer(refund).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'], url_path='cancel')
    @transaction.atomic
    def cancel_refund(self, request, pk=None):
        """Cancel a pending refund request"""
        refund = self.get_object()
        
        if refund.status != RefundStatus.PENDING:
            return Response(
                {"error": f"Only PENDING refunds can be cancelled"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund.status = RefundStatus.REJECTED
        refund.reason = "Cancelled by user"
        refund.processed_at = timezone.now()
        refund.save()
        
        logger.info(f"Refund {refund.id} cancelled")
        return Response(
            RefundSerializer(refund).data,
            status=status.HTTP_200_OK
        )


class HealthCheckView(APIView):
    """Health check endpoint"""
    
    def get(self, request):
        """Return health status"""
        return Response(
            {"status": "healthy", "timestamp": timezone.now()},
            status=status.HTTP_200_OK
        )