# BNPL Debt & Refund Service

A robust Debt & Refund Management microservice for BNPL (Buy Now, Pay Later) fintech platforms. This service handles installment plans, debt management, refund processing, and user status management with comprehensive data masking and idempotency support.

## Features

### Core Functionality
- **BNPL Plan Management**: Create and manage installment plans for eligible users
- **Debt Management**: Automatic overdue detection and user status management
- **Refund Processing**: Secure refund requests with merchant approval workflow
- **User Management**: Mock user data with sensitive information masking
- **Idempotency**: Prevents duplicate operations for payment and refund endpoints

### Security Features
- **Data Masking**: Personal and card information automatically masked in API responses
- **Secure Logging**: Prevents logging of sensitive personal details
- **Input Validation**: Comprehensive validation for all API endpoints

### Bonus Features
- **Async Processing**: Celery-based overdue payment checking
- **Webhook Support**: Refund status webhooks for merchant integration
- **Comprehensive Testing**: Full test coverage with pytest
- **API Documentation**: Swagger/OpenAPI documentation
- **Docker Support**: Containerized deployment with docker-compose

## Tech Stack

- **Backend**: Python 3.11+, Django 4.2.7, Django REST Framework
- **Database**: PostgreSQL
- **Cache/Message Broker**: Redis
- **Async Tasks**: Celery
- **Containerization**: Docker + docker-compose
- **Testing**: pytest, pytest-django
- **Documentation**: drf-yasg (Swagger/OpenAPI)

## Quick Start

### Prerequisites
- Python 3.11+
- Docker and docker-compose
- PostgreSQL (if running locally)

### Using Docker (Recommended)

1. **Clone and navigate to the project**
   ```bash
   cd bnpl-debt-refund-service
   ```

2. **Start the services**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - API: http://localhost:8000/api/v1/
   - Admin: http://localhost:8000/admin/
   - Swagger: http://localhost:8000/swagger/
   - ReDoc: http://localhost:8000/redoc/

### Local Development

1. **Set up virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Populate mock data**
   ```bash
   python manage.py populate_mock_data
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

## API Endpoints

### User Management
- `GET /api/v1/users/` - List all users (with masked data)
- `GET /api/v1/users/{user_id}/` - Get specific user (with masked data)

### BNPL Plans
- `GET /api/v1/plans/` - List all BNPL plans
- `POST /api/v1/plans/` - Create new BNPL plan
- `GET /api/v1/plans/{id}/` - Get specific plan details

### Debt Management
- `GET /api/v1/debt/{user_id}/` - Check user's debt status
- `POST /api/v1/debt/{user_id}/` - Process repayment

### Refund Management
- `GET /api/v1/refunds/` - List all refunds
- `POST /api/v1/refunds/` - Create refund request
- `POST /api/v1/refunds/{id}/approve/` - Approve/reject refund
- `POST /api/v1/refunds/{id}/cancel/` - Cancel pending refund

### Health Check
- `GET /api/v1/health/` - Service health status

## Data Models

### User
- `user_id`: Unique identifier
- `full_name`: User's full name
- `phone_number`: Contact phone number
- `passport_number`: Passport identifier
- `date_of_birth`: Birth date
- `card_info`: JSON containing card details
- `status`: NORMAL or DEBT_USER

### BNPL Plan
- `id`: Unique plan identifier
- `user`: Associated user
- `total_amount`: Total plan amount
- `status`: ACTIVE or COMPLETED

### Installment
- `id`: Unique installment identifier
- `plan`: Associated BNPL plan
- `amount_due`: Payment amount
- `due_date`: Payment due date
- `status`: UPCOMING, PAID, or OVERDUE

### Refund
- `id`: Unique refund identifier
- `user`: Associated user
- `transaction_id`: Unique transaction reference
- `amount`: Refund amount
- `status`: PENDING, APPROVED, REJECTED, or COMPLETED

## Data Masking

The service automatically masks sensitive information in API responses:

- **Card Numbers**: `4111 **** **** 1111`
- **Phone Numbers**: `+998****567`
- **Passport Numbers**: `AA*******`

## Idempotency

All payment and refund endpoints support idempotency:
- Use `X-Idempotency-Key` header with unique values
- Prevents duplicate processing of the same request
- Keys expire after 24 hours

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bnpl_service

# Run specific test file
pytest bnpl_service/tests.py::UserAPITest
```

## Celery Tasks

### Scheduled Tasks
- **Overdue Payment Checker**: Runs every 5 minutes
- **Idempotency Key Cleanup**: Runs every hour

### Manual Tasks
- **Refund Webhook Processing**: Process merchant webhooks

## Development

### Adding New Features
1. Create models in `bnpl_service/models.py`
2. Add serializers in `bnpl_service/serializers.py`
3. Implement views in `bnpl_service/views.py`
4. Add URL patterns in `bnpl_service/urls.py`
5. Write tests in `bnpl_service/tests.py`

### Code Style
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings for all functions and classes
- Maintain test coverage above 90%

## Deployment

### Production Considerations
- Set `DEBUG=False` in production
- Use environment variables for sensitive configuration
- Configure proper database connection pooling
- Set up monitoring and logging
- Use HTTPS in production
- Configure CORS properly for production domains

### Environment Variables
```bash
SECRET_KEY=your-secure-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_NAME=production_db_name
DB_USER=production_db_user
DB_PASSWORD=secure_password
DB_HOST=your_db_host
DB_PORT=5432
REDIS_URL=redis://your_redis_host:6379/0
CELERY_BROKER_URL=redis://your_redis_host:6379/0
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the BSD License - see the LICENSE file for details.

## Support

For questions and support, please contact the development team or create an issue in the repository.
