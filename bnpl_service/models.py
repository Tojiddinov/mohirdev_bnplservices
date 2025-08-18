from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid


def generate_user_id():
    """Generate a unique user ID in the format mock-usr-XXX"""
    last_user = User.objects.order_by('created_at').last()
    if last_user:
        # Extract number from last user_id (e.g., 'mock-usr-003' -> 3)
        try:
            last_number = int(last_user.user_id.split('-')[-1])
            new_number = last_number + 1
        except (ValueError, IndexError):
            # Fallback if the format is unexpected
            new_number = User.objects.count() + 1
    else:
        new_number = 1
    
    return f"mock-usr-{new_number:03d}"


class UserStatus(models.TextChoices):
    NORMAL = 'NORMAL', 'Normal'
    DEBT_USER = 'DEBT_USER', 'Debt User'


class RefundStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    COMPLETED = 'COMPLETED', 'Completed'


class InstallmentStatus(models.TextChoices):
    UPCOMING = 'UPCOMING', 'Upcoming'
    PAID = 'PAID', 'Paid'
    OVERDUE = 'OVERDUE', 'Overdue'


class PlanStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'


class User(models.Model):
    """Mock User model for BNPL system"""
    user_id = models.CharField(max_length=100, primary_key=True, default=generate_user_id)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    personal_info = models.JSONField(help_text="Stores sensitive user information", null=True, blank=True)
    passport_number = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    card_info = models.JSONField(help_text="Stores card information", null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.NORMAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['phone_number']),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.full_name}"

    def mask_personal_info(self):
        """Returns masked version of personal information"""
        # Safely handle card_info in case it's not a dict (data corruption)
        card_number = "****"
        if self.card_info and isinstance(self.card_info, dict):
            card_info_number = self.card_info.get('card_number', '')
            if card_info_number and len(str(card_info_number)) >= 8:
                card_str = str(card_info_number)
                card_number = f"{card_str[:4]} **** **** {card_str[-4:]}"
        
        return {
            "full_name": self.full_name,
            "phone_number": f"+{self.phone_number[:3]}****{self.phone_number[-4:]}",
            "passport_number": "AA*******",
            "card_number": card_number
        }


class BNPLPlan(models.Model):
    """BNPL Plan model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bnpl_plans')
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20,
        choices=PlanStatus.choices,
        default=PlanStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bnpl_plans'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Plan {self.id} - User {self.user_id} - {self.total_amount}"


class Installment(models.Model):
    """Installment model for BNPL plans"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(BNPLPlan, on_delete=models.CASCADE, related_name='installments')
    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    due_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=InstallmentStatus.choices,
        default=InstallmentStatus.UPCOMING
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'installments'
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Installment {self.id} - Plan {self.plan_id} - {self.amount_due}"

    def is_overdue(self):
        """Check if installment is overdue"""
        return (
            self.status == InstallmentStatus.UPCOMING and
            self.due_date < timezone.now().date()
        )


class Refund(models.Model):
    """Refund model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refunds')
    transaction_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING
    )
    reason = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'refunds'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Refund {self.id} - User {self.user_id} - {self.amount}"


class IdempotencyKey(models.Model):
    """Model to store idempotency keys for preventing duplicate operations"""
    key = models.CharField(max_length=255, unique=True, primary_key=True)
    response_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'idempotency_keys'
        indexes = [
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Idempotency Key: {self.key}"