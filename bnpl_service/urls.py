from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'plans', views.BNPLPlanViewSet, basename='bnpl-plan')
router.register(r'refunds', views.RefundViewSet, basename='refund')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
    path('debt/<str:user_id>/', views.DebtManagementView.as_view(), name='debt-management'),
    path('health/', views.HealthCheckView.as_view(), name='health-check'),
]
