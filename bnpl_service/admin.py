from django.contrib import admin
from django.utils.html import format_html
from .models import User, BNPLPlan, Installment, Refund, IdempotencyKey


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'full_name', 'phone_number', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user_id', 'full_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user_id', 'full_name', 'phone_number', 'status')
        }),
        ('Personal Information', {
            'fields': ('passport_number', 'date_of_birth'),
            'classes': ('collapse',)
        }),
        ('Card Information', {
            'fields': ('card_info',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BNPLPlan)
class BNPLPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_id', 'total_amount', 'status', 'installment_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'user__user_id', 'user__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def user_id(self, obj):
        return obj.user.user_id
    user_id.short_description = 'User ID'
    
    def installment_count(self, obj):
        return obj.installments.count()
    installment_count.short_description = 'Installments'


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'plan_id', 'user_id', 'amount_due', 'due_date', 'status', 'is_overdue_display']
    list_filter = ['status', 'due_date', 'created_at']
    search_fields = ['id', 'plan__id', 'plan__user__user_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def plan_id(self, obj):
        return obj.plan.id
    plan_id.short_description = 'Plan ID'
    
    def user_id(self, obj):
        return obj.plan.user.user_id
    user_id.short_description = 'User ID'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue():
            return format_html('<span style="color: red;">OVERDUE</span>')
        return format_html('<span style="color: green;">OK</span>')
    is_overdue_display.short_description = 'Overdue Status'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_id', 'transaction_id', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'user__user_id', 'transaction_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def user_id(self, obj):
        return obj.user.user_id
    user_id.short_description = 'User ID'
    
    actions = ['approve_refunds', 'reject_refunds']
    
    def approve_refunds(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status='PENDING').update(
            status='APPROVED',
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated} refunds were approved.')
    approve_refunds.short_description = "Approve selected refunds"
    
    def reject_refunds(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status='PENDING').update(
            status='REJECTED',
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated} refunds were rejected.')
    reject_refunds.short_description = "Reject selected refunds"


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ['key', 'created_at', 'expires_at', 'is_expired']
    list_filter = ['created_at', 'expires_at']
    search_fields = ['key']
    readonly_fields = ['key', 'created_at']
    
    def is_expired(self, obj):
        from django.utils import timezone
        return obj.expires_at < timezone.now()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
