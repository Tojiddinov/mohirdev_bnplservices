from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta
import uuid

from .models import User, BNPLPlan, Installment, Refund, UserStatus, PlanStatus, InstallmentStatus, RefundStatus


class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='test-user-001',
            full_name='Test User',
            phone_number='+998901234567',
            passport_number='AA1234567',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '4111111111111111', 'expiry': '12/26'},
            status=UserStatus.NORMAL
        )

    def test_user_creation(self):
        self.assertEqual(self.user.user_id, 'test-user-001')
        self.assertEqual(self.user.full_name, 'Test User')
        self.assertEqual(self.user.status, UserStatus.NORMAL)

    def test_user_masking(self):
        masked_info = self.user.mask_personal_info()
        self.assertEqual(masked_info['full_name'], 'Test User')
        self.assertIn('****', masked_info['phone_number'])
        self.assertEqual(masked_info['passport_number'], 'AA*******')
        self.assertIn('****', masked_info['card_number'])


class BNPLPlanModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='test-user-002',
            full_name='Test User 2',
            phone_number='+998901234568',
            passport_number='AA1234568',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '5555555555554444', 'expiry': '10/25'},
            status=UserStatus.NORMAL
        )
        self.plan = BNPLPlan.objects.create(
            user=self.user,
            total_amount=Decimal('1000.00'),
            status=PlanStatus.ACTIVE
        )

    def test_plan_creation(self):
        self.assertEqual(self.plan.user, self.user)
        self.assertEqual(self.plan.total_amount, Decimal('1000.00'))
        self.assertEqual(self.plan.status, PlanStatus.ACTIVE)


class InstallmentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='test-user-003',
            full_name='Test User 3',
            phone_number='+998901234569',
            passport_number='AA1234569',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '378282246310005', 'expiry': '08/24'},
            status=UserStatus.NORMAL
        )
        self.plan = BNPLPlan.objects.create(
            user=self.user,
            total_amount=Decimal('900.00'),
            status=PlanStatus.ACTIVE
        )
        self.installment = Installment.objects.create(
            plan=self.plan,
            amount_due=Decimal('300.00'),
            due_date=date.today() + timedelta(days=30),
            status=InstallmentStatus.UPCOMING
        )

    def test_installment_creation(self):
        self.assertEqual(self.installment.plan, self.plan)
        self.assertEqual(self.installment.amount_due, Decimal('300.00'))
        self.assertEqual(self.installment.status, InstallmentStatus.UPCOMING)

    def test_overdue_check(self):
        # Test not overdue
        self.assertFalse(self.installment.is_overdue())
        
        # Test overdue
        overdue_installment = Installment.objects.create(
            plan=self.plan,
            amount_due=Decimal('300.00'),
            due_date=date.today() - timedelta(days=1),
            status=InstallmentStatus.UPCOMING
        )
        self.assertTrue(overdue_installment.is_overdue())


class RefundModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='test-user-004',
            full_name='Test User 4',
            phone_number='+998901234570',
            passport_number='AA1234570',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '4111111111111111', 'expiry': '12/26'},
            status=UserStatus.NORMAL
        )
        self.refund = Refund.objects.create(
            user=self.user,
            transaction_id='TXN123456',
            amount=Decimal('100.00'),
            status=RefundStatus.PENDING
        )

    def test_refund_creation(self):
        self.assertEqual(self.refund.user, self.user)
        self.assertEqual(self.refund.transaction_id, 'TXN123456')
        self.assertEqual(self.refund.amount, Decimal('100.00'))
        self.assertEqual(self.refund.status, RefundStatus.PENDING)


class UserAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='api-test-user',
            full_name='API Test User',
            phone_number='+998901234571',
            passport_number='AA1234571',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '4111111111111111', 'expiry': '12/26'},
            status=UserStatus.NORMAL
        )

    def test_list_users(self):
        url = reverse('user-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_retrieve_user(self):
        url = reverse('user-detail', kwargs={'user_id': self.user.user_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_id'], self.user.user_id)
        # Check that sensitive data is masked
        self.assertIn('****', response.data['card_number'])


class BNPLPlanAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='plan-test-user',
            full_name='Plan Test User',
            phone_number='+998901234572',
            passport_number='AA1234572',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '5555555555554444', 'expiry': '10/25'},
            status=UserStatus.NORMAL
        )

    def test_create_plan_success(self):
        url = reverse('bnpl-plan-list')
        data = {
            'user_id': self.user.user_id,
            'total_amount': '1500.00',
            'installment_count': 3
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_amount'], '1500.00')
        self.assertEqual(len(response.data['installments']), 3)

    def test_create_plan_debt_user_forbidden(self):
        # Change user to debt status
        self.user.status = UserStatus.DEBT_USER
        self.user.save()
        
        url = reverse('bnpl-plan-list')
        data = {
            'user_id': self.user.user_id,
            'total_amount': '1500.00',
            'installment_count': 3
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('DEBT_USER status cannot create new BNPL plans', str(response.data))

    def test_create_plan_invalid_user(self):
        url = reverse('bnpl-plan-list')
        data = {
            'user_id': 'non-existent-user',
            'total_amount': '1500.00',
            'installment_count': 3
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DebtManagementAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='debt-test-user',
            full_name='Debt Test User',
            phone_number='+998901234573',
            passport_number='AA1234573',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '378282246310005', 'expiry': '08/24'},
            status=UserStatus.NORMAL
        )
        self.plan = BNPLPlan.objects.create(
            user=self.user,
            total_amount=Decimal('900.00'),
            status=PlanStatus.ACTIVE
        )
        # Create overdue installment
        self.overdue_installment = Installment.objects.create(
            plan=self.plan,
            amount_due=Decimal('300.00'),
            due_date=date.today() - timedelta(days=5),
            status=InstallmentStatus.OVERDUE
        )

    def test_debt_check(self):
        url = reverse('debt-management', kwargs={'user_id': self.user.user_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['has_overdue'])
        self.assertEqual(response.data['total_debt'], '300.00')

    def test_repayment_success(self):
        url = reverse('debt-management', kwargs={'user_id': self.user.user_id})
        data = {
            'installment_ids': [str(self.overdue_installment.id)]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['paid_installments'], 1)
        
        # Check installment status updated
        self.overdue_installment.refresh_from_db()
        self.assertEqual(self.overdue_installment.status, InstallmentStatus.PAID)


class RefundAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id='refund-test-user',
            full_name='Refund Test User',
            phone_number='+998901234574',
            passport_number='AA1234574',
            date_of_birth=date(1990, 1, 1),
            card_info={'card_number': '4111111111111111', 'expiry': '12/26'},
            status=UserStatus.NORMAL
        )

    def test_create_refund_success(self):
        url = reverse('refund-list')
        data = {
            'user_id': self.user.user_id,
            'transaction_id': 'TXN789012',
            'amount': '75.50',
            'reason': 'Product defect'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['amount'], '75.50')
        self.assertEqual(response.data['status'], RefundStatus.PENDING)

    def test_create_refund_idempotency(self):
        url = reverse('refund-list')
        data = {
            'user_id': self.user.user_id,
            'transaction_id': 'TXN789013',
            'amount': '100.00'
        }
        
        # First request
        response1 = self.client.post(url, data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second request with same transaction_id
        response2 = self.client.post(url, data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data['id'], response2.data['id'])

    def test_approve_refund(self):
        refund = Refund.objects.create(
            user=self.user,
            transaction_id='TXN789014',
            amount=Decimal('50.00'),
            status=RefundStatus.PENDING
        )
        
        url = reverse('refund-approve-refund', kwargs={'pk': refund.id})
        data = {'action': 'approve'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], RefundStatus.APPROVED)

    def test_cancel_refund(self):
        refund = Refund.objects.create(
            user=self.user,
            transaction_id='TXN789015',
            amount=Decimal('25.00'),
            status=RefundStatus.PENDING
        )
        
        url = reverse('refund-cancel-refund', kwargs={'pk': refund.id})
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], RefundStatus.REJECTED)


class HealthCheckAPITest(APITestCase):
    def test_health_check(self):
        url = reverse('health-check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertIn('timestamp', response.data)
