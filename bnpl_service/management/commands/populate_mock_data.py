from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import json

from bnpl_service.models import User, BNPLPlan, Installment, UserStatus, PlanStatus, InstallmentStatus


class Command(BaseCommand):
    help = 'Populate database with mock BNPL data'

    def handle(self, *args, **options):
        self.stdout.write('Creating mock data...')
        
        # Create mock users
        users_data = [
            {
                'user_id': 'mock-usr-001',
                'full_name': 'John Doe',
                'phone_number': '+998901234567',
                'passport_number': 'AA1234567',
                'date_of_birth': date(1990, 5, 20),
                'card_info': {
                    'card_number': '4111111111111111',
                    'expiry': '12/26'
                },
                'status': UserStatus.NORMAL
            },
            {
                'user_id': 'mock-usr-002',
                'full_name': 'Jane Smith',
                'phone_number': '+998901234568',
                'passport_number': 'AA1234568',
                'date_of_birth': date(1985, 8, 15),
                'card_info': {
                    'card_number': '5555555555554444',
                    'expiry': '10/25'
                },
                'status': UserStatus.NORMAL
            },
            {
                'user_id': 'mock-usr-003',
                'full_name': 'Bob Johnson',
                'phone_number': '+998901234569',
                'passport_number': 'AA1234569',
                'date_of_birth': date(1992, 3, 10),
                'card_info': {
                    'card_number': '378282246310005',
                    'expiry': '08/24'
                },
                'status': UserStatus.DEBT_USER
            }
        ]
        
        created_users = []
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                user_id=user_data['user_id'],
                defaults=user_data
            )
            if created:
                self.stdout.write(f'Created user: {user.full_name}')
            else:
                self.stdout.write(f'User already exists: {user.full_name}')
            created_users.append(user)
        
        # Create BNPL plans for normal users
        for user in created_users:
            if user.status == UserStatus.NORMAL:
                # Create active plan
                plan = BNPLPlan.objects.create(
                    user=user,
                    total_amount=Decimal('1500.00'),
                    status=PlanStatus.ACTIVE
                )
                
                # Create installments
                installment_amount = Decimal('500.00')
                current_date = date.today()
                
                for i in range(3):
                    due_date = current_date + timedelta(days=30 * (i + 1))
                    status = InstallmentStatus.UPCOMING
                    
                    # Make first installment overdue for demonstration
                    if i == 0:
                        due_date = current_date - timedelta(days=5)
                        status = InstallmentStatus.OVERDUE
                    
                    Installment.objects.create(
                        plan=plan,
                        amount_due=installment_amount,
                        due_date=due_date,
                        status=status
                    )
                
                self.stdout.write(f'Created BNPL plan for {user.full_name}: {plan.id}')
        
        # Create overdue installments for debt user
        debt_user = User.objects.filter(status=UserStatus.DEBT_USER).first()
        if debt_user:
            plan = BNPLPlan.objects.create(
                user=debt_user,
                total_amount=Decimal('2000.00'),
                status=PlanStatus.ACTIVE
            )
            
            # Create overdue installments
            installment_amount = Decimal('500.00')
            current_date = date.today()
            
            for i in range(4):
                due_date = current_date - timedelta(days=15 * (i + 1))
                Installment.objects.create(
                    plan=plan,
                    amount_due=installment_amount,
                    due_date=due_date,
                    status=InstallmentStatus.OVERDUE
                )
            
            self.stdout.write(f'Created overdue BNPL plan for debt user {debt_user.full_name}: {plan.id}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created mock data!')
        )
        
        # Display summary
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'- Users: {User.objects.count()}')
        self.stdout.write(f'- BNPL Plans: {BNPLPlan.objects.count()}')
        self.stdout.write(f'- Installments: {Installment.objects.count()}')
        self.stdout.write(f'- Normal Users: {User.objects.filter(status=UserStatus.NORMAL).count()}')
        self.stdout.write(f'- Debt Users: {User.objects.filter(status=UserStatus.DEBT_USER).count()}')
