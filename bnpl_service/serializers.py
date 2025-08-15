from rest_framework import serializers
from .models import User, BNPLPlan, Installment, Refund
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class MaskedUserSerializer(serializers.ModelSerializer):
    """Serializer for User with masked sensitive information"""
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    passport_number = serializers.SerializerMethodField()
    card_number = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['user_id', 'full_name', 'phone_number', 'passport_number', 
                  'date_of_birth', 'card_number', 'status', 'created_at']
        read_only_fields = ['user_id', 'created_at']

    def get_full_name(self, obj):
        return obj.full_name

    def get_phone_number(self, obj):
        phone = obj.phone_number
        if len(phone) > 7:
            return f"+{phone[:3]}****{phone[-4:]}"
        return "****"

    def get_passport_number(self, obj):
        return "AA*******"

    def get_card_number(self, obj):
        card_info = obj.card_info or {}
        card_number = card_info.get('card_number', '')
        if card_number and len(card_number) >= 8:
            return f"{card_number[:4]} **** **** {card_number[-4:]}"
        return "**** **** **** ****"


class InstallmentSerializer(serializers.ModelSerializer):
    """Serializer for Installment"""
    
    class Meta:
        model = Installment
        fields = ['id', 'plan_id', 'amount_due', 'due_date', 'status', 
                  'paid_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class BNPLPlanSerializer(serializers.ModelSerializer):
    """Serializer for BNPL Plan"""
    installments = InstallmentSerializer(many=True, read_only=True)
    user = MaskedUserSerializer(read_only=True)
    
    class Meta:
        model = BNPLPlan
        fields = ['id', 'user', 'user_id', 'total_amount', 'status', 
                  'installments', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class CreateBNPLPlanSerializer(serializers.Serializer):
    """Serializer for creating a new BNPL Plan"""
    user_id = serializers.CharField(max_length=100)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    installment_count = serializers.IntegerField(min_value=1, max_value=12, default=3)
    
    def validate_user_id(self, value):
        """Validate that user exists and is eligible for new plan"""
        try:
            user = User.objects.get(user_id=value)
            if user.status == 'DEBT_USER':
                raise serializers.ValidationError(
                    "User with DEBT_USER status cannot create new BNPL plans"
                )
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund"""
    user = MaskedUserSerializer(read_only=True)
    
    class Meta:
        model = Refund
        fields = ['id', 'user', 'user_id', 'transaction_id', 'amount', 
                  'status', 'reason', 'processed_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'processed_at', 'created_at', 'updated_at']


class CreateRefundSerializer(serializers.Serializer):
    """Serializer for creating a refund request"""
    user_id = serializers.CharField(max_length=100)
    transaction_id = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate_transaction_id(self, value):
        """Ensure transaction_id is unique"""
        if Refund.objects.filter(transaction_id=value).exists():
            raise serializers.ValidationError(
                "A refund with this transaction ID already exists"
            )
        return value
    
    def validate_user_id(self, value):
        """Validate that user exists"""
        if not User.objects.filter(user_id=value).exists():
            raise serializers.ValidationError("User not found")
        return value


class RefundApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting refunds"""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True)


class DebtCheckSerializer(serializers.Serializer):
    """Serializer for debt check response"""
    user_id = serializers.CharField()
    has_overdue = serializers.BooleanField()
    total_debt = serializers.DecimalField(max_digits=12, decimal_places=2)
    overdue_installments = InstallmentSerializer(many=True)


class RepaymentSerializer(serializers.Serializer):
    """Serializer for repayment request"""
    installment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    
    def validate_installment_ids(self, value):
        """Validate that all installments exist and are overdue"""
        installments = Installment.objects.filter(id__in=value)
        if installments.count() != len(value):
            raise serializers.ValidationError("Some installment IDs are invalid")
        
        for installment in installments:
            if installment.status != 'OVERDUE':
                raise serializers.ValidationError(
                    f"Installment {installment.id} is not overdue"
                )
        return value
