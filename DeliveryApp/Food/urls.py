from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings
from .views import PasswordResetView, VerifyOTPView

urlpatterns = [
    # Standard Django Views
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('menu/', views.menu_view, name='menu'),
    path('reservation/', views.reservation_view, name='reservation'),
    path('logout/', views.logout_view, name='logout'),

    # API Views for Cart
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('get-cart-items/', views.get_cart_items, name='get_cart_items'),
    path('delete-cart-item/', views.delete_cart_item, name='delete_cart_item'),
    path('update-cart-item/', views.update_cart_item, name='update_cart_item'),
    path('submit-order/', views.submit_order, name='submit_order'),

    # API Views for Orders
    path('get-order-history/', views.get_order_history, name='get_order_history'),
    
    path('update_order/<int:order_id>/<str:new_status>/', views.update_order_status, name='update_order_status'),

    # API Views for Reservations
    path('submit-reservation/', views.submit_reservation, name='submit_reservation'),
    path('get-reservations/', views.get_reservations, name='get_reservations'),
    path('cancel-reservation/', views.cancel_reservation, name='cancel_reservation'),

    # API Views for Notifications
    path('get-notifications/', views.get_notifications, name='get_notifications'),
    path('add-notification/', views.add_notification, name='add_notification'),
    path('mark-notification-read/', views.mark_notification_read, name='mark_notification_read'),

    # API Views for Rewards
    path('get_rewards/', views.get_rewards, name='get_rewards'),
    path('add_reward_points/', views.add_reward_points, name='add_reward_points'),
    path('redeem_reward/', views.redeem_reward, name='redeem_reward'),

    # API Views for Support
    path('submit-support-request/', views.submit_support_request, name='submit_support_request'),

    # API Views for Profile
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    # Django REST Framework API Views
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    
    # favorite dishs
    path('get_favorites/', views.get_favorites, name='get_favorites'),
    path('add_to_favorites/', views.add_to_favorites, name='add_to_favorites'),
    path('remove_from_favorites/', views.remove_from_favorites, name='remove_from_favorites'),
    
    # analytics_dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    
]