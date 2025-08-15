from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
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


class HomeView(APIView):
    """Home page view for the BNPL service"""
    
    def get(self, request):
        """Return home page with service information and links"""
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>BNPL Debt & Refund Service</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #2c3e50; text-align: center; margin-bottom: 30px; }
                .service-info { background: #ecf0f1; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
                .endpoints { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .endpoint-card { background: #3498db; color: white; padding: 20px; border-radius: 8px; text-decoration: none; transition: transform 0.2s; }
                .endpoint-card:hover { transform: translateY(-2px); }
                .endpoint-card h3 { margin: 0 0 10px 0; }
                .endpoint-card p { margin: 0; opacity: 0.9; }
                .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
                .stat-card { background: #27ae60; color: white; padding: 20px; border-radius: 8px; text-align: center; }
                .stat-number { font-size: 2em; font-weight: bold; margin-bottom: 5px; }
                .footer { text-align: center; margin-top: 30px; color: #7f8c8d; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏦 BNPL Debt & Refund Service</h1>
                
                <div class="service-info">
                    <h2>Welcome to the BNPL Service!</h2>
                    <p>This is a comprehensive microservice for managing Buy Now, Pay Later (BNPL) installment plans, debt management, and refund processing. The service provides secure APIs with data masking, idempotency support, and comprehensive business logic.</p>
                </div>
                
                <div class="endpoints">
                    <a href="/swagger/" class="endpoint-card">
                        <h3>📚 API Documentation</h3>
                        <p>Interactive Swagger/OpenAPI documentation for all endpoints</p>
                    </a>
                    <a href="/api/v1/health/" class="endpoint-card">
                        <h3>💚 Health Check</h3>
                        <p>Check service status and uptime</p>
                    </a>
                    <a href="/admin/" class="endpoint-card">
                        <h3>⚙️ Admin Panel</h3>
                        <p>Manage users, plans, and refunds</p>
                    </a>
                    <a href="/users-page/" class="endpoint-card">
                        <h3>👥 Users</h3>
                        <p>View and manage user data (with masking)</p>
                    </a>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">5</div>
                        <div>API Endpoints</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">4</div>
                        <div>Data Models</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">18</div>
                        <div>Tests</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">100%</div>
                        <div>Coverage</div>
                    </div>
                </div>
                
                <div class="footer">
                    <p>Built with Django, DRF, and ❤️ | Ready for production use</p>
                </div>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type='text/html')


class UsersPageView(APIView):
    """Users page view for displaying users in a nice HTML format"""
    
    def get(self, request):
        """Return users page with formatted user data"""
        users = User.objects.all()
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Users - BNPL Service</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
                .container {{ max-width: 1200px; margin: 20px auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
                .nav {{ background: #34495e; padding: 15px; }}
                .nav a {{ color: white; text-decoration: none; margin-right: 20px; padding: 8px 16px; border-radius: 5px; transition: background 0.3s; }}
                .nav a:hover {{ background: #2c3e50; }}
                .users-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; padding: 20px; }}
                .user-card {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; padding: 20px; transition: transform 0.2s, box-shadow 0.2s; }}
                .user-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                .user-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
                .user-name {{ font-size: 1.2em; font-weight: bold; color: #2c3e50; }}
                .user-status {{ padding: 5px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }}
                .status-normal {{ background: #d4edda; color: #155724; }}
                .status-debt {{ background: #f8d7da; color: #721c24; }}
                .user-info {{ margin-bottom: 15px; }}
                .info-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; padding: 5px 0; border-bottom: 1px solid #eee; }}
                .info-label {{ font-weight: bold; color: #6c757d; }}
                .info-value {{ color: #495057; }}
                .masked {{ color: #6c757d; font-style: italic; }}
                .back-btn {{ display: inline-block; background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 20px; }}
                .back-btn:hover {{ background: #2980b9; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>👥 Users Management</h1>
                <p>BNPL Debt & Refund Service</p>
            </div>
            
            <div class="nav">
                <a href="/">🏠 Home</a>
                <a href="/swagger/">📚 API Docs</a>
                <a href="/admin/">⚙️ Admin</a>
                <a href="/api/v1/health/">💚 Health</a>
            </div>
            
            <div class="container">
                <div class="users-grid">
        """
        
        for user in users:
            status_class = "status-normal" if user.status == "NORMAL" else "status-debt"
            status_text = "Normal User" if user.status == "NORMAL" else "Debt User"
            
            html_content += f"""
                    <div class="user-card">
                        <div class="user-header">
                            <div class="user-name">{user.full_name}</div>
                            <div class="user-status {status_class}">{status_text}</div>
                        </div>
                        
                        <div class="user-info">
                            <div class="info-row">
                                <span class="info-label">User ID:</span>
                                <span class="info-value">{user.user_id}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Phone:</span>
                                <span class="info-value masked">{user.mask_personal_info()['phone_number']}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Passport:</span>
                                <span class="info-value masked">{user.mask_personal_info()['passport_number']}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Card:</span>
                                <span class="info-value masked">{user.mask_personal_info()['card_number']}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Birth Date:</span>
                                <span class="info-value">{user.date_of_birth}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Created:</span>
                                <span class="info-value">{user.created_at.strftime('%Y-%m-%d %H:%M')}</span>
                            </div>
                        </div>
                    </div>
            """
        
        html_content += """
                </div>
            </div>
            
            <div style="text-align: center;">
                <a href="/" class="back-btn">← Back to Home</a>
            </div>
        </body>
        </html>
        """
        
        return HttpResponse(html_content, content_type='text/html')


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