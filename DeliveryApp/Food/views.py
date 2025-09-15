from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Dish, CartItem, Order, Reservation, User, PasswordReset, Notification,Favorite, Reward,RedeemedReward, UserReward, SupportRequest, Profile, OrderItem
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
import random
import json
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import string
from django.core.mail import send_mail
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum, Count
from datetime import timedelta
from django.db.models.functions import TruncDay

from channels.layers import get_channel_layer # type: ignore
from asgiref.sync import async_to_sync


def home(request):
    return render(request, 'home.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        messages.error(request, 'Invalid credentials')
    return render(request, 'login.html')


def signup_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        if password1 != password2:
            messages.error(request, 'Passwords do not match')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
        else:
            user = User.objects.create_user(username=username, email=email, password=password1)
            login(request, user)
            return redirect('menu')
    return render(request, 'login.html')


def reservation_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'reservation.html')


# API Views
class PasswordResetView(APIView):
    def post(self, request):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({'status': 'error', 'message': 'User not found'}, status=404)
        otp = ''.join(random.choices(string.digits, k=6))
        PasswordReset.objects.create(user=user, otp=otp)
        send_mail(
            'Password Reset OTP',
            f'Your OTP: {otp}',
            'from@example.com',
            [email],
            fail_silently=False,
        )
        return Response({'status': 'success', 'message': 'OTP sent to your email'})


class VerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')
        reset = PasswordReset.objects.filter(user__email=email, otp=otp).first()
        if reset and reset.expires_at > timezone.now():
            user = reset.user
            user.set_password(new_password)
            user.save()
            reset.delete()
            return Response({'status': 'success', 'message': 'Password reset successful'})
  
        return Response({'status': 'error', 'message': 'Invalid or expired OTP'}, status=400)


@login_required
def analytics_dashboard(request):
    total_sales = Order.objects.filter(status='delivered').aggregate(total_sales=Sum('total'))['total_sales'] or 0

    # Daily Sales (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    daily_sales = Order.objects.filter(
        status='delivered',
        created_at__gte=seven_days_ago
    ).annotate(day=TruncDay('created_at')).values('day').annotate(sales=Sum('total')).order_by('day')

    daily_sales_data = {
        'labels': [entry['day'].strftime('%Y-%m-%d') for entry in daily_sales],
        'data': [float(entry['sales']) for entry in daily_sales]
    }

    
    popular_items = OrderItem.objects.filter(
        order__status='delivered'
    ).values('dish__name').annotate(total_quantity=Sum('quantity')).order_by('-total_quantity')[:5]

    popular_items_data = {
        'labels': [item['dish__name'] for item in popular_items],
        'data': [item['total_quantity'] for item in popular_items]
    }

    return JsonResponse({
        'status': 'success',
        'total_sales': float(total_sales),
        'daily_sales_data': daily_sales_data,
        'popular_items_data': popular_items_data,
    })

@login_required
def add_to_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        price = data.get('price')
        quantity = data.get('quantity', 1)

        dish = get_object_or_404(Dish, id=dish_id)
        # Check if the item is already in the cart
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            dish=dish,
            defaults={'quantity': quantity}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        return JsonResponse({'status': 'success', 'message': 'Item added to cart'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def update_cart_item(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            change = data.get('change')

            cart_item = CartItem.objects.filter(id=item_id, user=request.user).first()
            if not cart_item:
                return JsonResponse({'status': 'error', 'message': 'Cart item not found'})

            cart_item.quantity += change
            if cart_item.quantity <= 0:
                cart_item.delete()
            else:
                cart_item.save()

            return JsonResponse({'status': 'success', 'message': 'Quantity updated'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


def menu_view(request):
    dishes = Dish.objects.order_by('?')[:6]
    cart_items = CartItem.objects.filter(user=request.user) if request.user.is_authenticated else []
    total = sum(item.total_price() for item in cart_items)
    orders = Order.objects.filter(user=request.user) if request.user.is_authenticated else []
    return render(request, 'menu.html', {
        'dishes': dishes,
        'cart_items': cart_items,
        'total': total,
        'orders': orders
    })


@login_required
def get_cart_items(request):
    print(f"User: {request.user.username}, Authenticated: {request.user.is_authenticated}")
    cart_items = CartItem.objects.filter(user=request.user)
    print(f"Cart items found: {cart_items.count()}")
    for item in cart_items:
        print(f"Item: {item.dish.name}, Quantity: {item.quantity}, User: {item.user.username}")
    cart_data = [
        {
            'id': item.id,
            'dish_name': item.dish.name,
            'price': float(item.dish.price),
            'quantity': item.quantity,
            'total_price': float(item.total_price())
        }
        for item in cart_items
    ]
    print(f"Cart data: {cart_data}")
    return JsonResponse({'status': 'success', 'cart_items': cart_data})


@login_required
def delete_cart_item(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')

            if not item_id:
                return JsonResponse({'status': 'error', 'message': 'Item ID is required'})

            # Delete the cart item
            cart_item = CartItem.objects.filter(id=item_id, user=request.user).first()
            if not cart_item:
                return JsonResponse({'status': 'error', 'message': 'Cart item not found'})

            cart_item.delete()
            return JsonResponse({'status': 'success', 'message': 'Item removed from cart'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def get_favorites(request):
    try:
        # Fetch the user's favorite dishes
        favorites = Favorite.objects.filter(user=request.user).select_related('dish')
        favorites_list = [
            {
                'id': favorite.dish.id,
                'name': favorite.dish.name,
                'price': float(favorite.dish.price),  
                'image': favorite.dish.image.url if favorite.dish.image else None
            }
            for favorite in favorites
        ]
        return JsonResponse({'status': 'success', 'favorites': favorites_list})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def add_to_favorites(request):
    try:
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        dish = Dish.objects.get(id=dish_id)

        # Check if the dish is already favorited
        if Favorite.objects.filter(user=request.user, dish=dish).exists():
            return JsonResponse({'status': 'error', 'message': 'Dish already in favorites'})

        # Add the dish to the user's favorites
        Favorite.objects.create(user=request.user, dish=dish)
        return JsonResponse({'status': 'success'})
    except Dish.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Dish not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def remove_from_favorites(request):
    try:
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        dish = Dish.objects.get(id=dish_id)

        # Remove the dish from the user's favorites
        favorite = Favorite.objects.filter(user=request.user, dish=dish)
        if favorite.exists():
            favorite.delete()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Dish not in favorites'})
    except Dish.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Dish not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def get_order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    orders_data = []
    for order in orders:
        items = [
            {
                'dish_name': item.dish.name,
                'quantity': item.quantity,
                'price': float(item.price)
            }
            for item in order.order_items.all()
        ]
        orders_data.append({
            'id': order.id,
            'created_at': order.created_at.isoformat(),
            'items': items,
            'total': float(order.total),
            'status': order.status
        })
    return JsonResponse({'status': 'success', 'orders': orders_data})


@login_required
def get_reservations(request):
    reservations = Reservation.objects.filter(user=request.user).values(
        'id', 'date', 'time', 'people', 'first_name', 'last_name', 'status'
    )
    return JsonResponse({
        'status': 'success',
        'reservations': list(reservations)
    })

@csrf_exempt
@login_required
def submit_reservation(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    try:
        # Parse JSON body
        data = json.loads(request.body)
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        phone = data.get('phone')
        email = data.get('email')
        date_str = data.get('date')  # YYYY-MM-DD
        time_str = data.get('time')  # HH:MM
        people = data.get('people')

        # Validate required fields
        if not all([first_name, last_name, phone, email, date_str, time_str, people]):
            return JsonResponse({'status': 'error', 'message': 'All fields are required'}, status=400)

        # Parse date and time
        try:
            reservation_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            reservation_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid date or time format'}, status=400)

        # Validate people
        try:
            people_int = int(people)
            if people_int < 1:
                raise ValueError
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Number of people must be a positive integer'}, status=400)

        # Create the reservation
        reservation = Reservation.objects.create(
            user=request.user,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            date=reservation_date,
            time=reservation_time,
            people=str(people),  
            status='Pending'
        )

        # Add notification
        Notification.objects.create(
            user=request.user,
            message=f"Reservation #{reservation.id} booked for {date_str} at {time_str}"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Reservation booked successfully',
            'reservation_id': reservation.id
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Server error: {str(e)}'}, status=500)
    
    
    
@csrf_exempt
@login_required
def cancel_reservation(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    try:
        data = json.loads(request.body)
        reservation_id = data.get('reservation_id')

        if not reservation_id:
            return JsonResponse({'status': 'error', 'message': 'Reservation ID is required'}, status=400)

        reservation = Reservation.objects.get(id=reservation_id, user=request.user)
        if reservation.status != 'Pending':
            return JsonResponse({'status': 'error', 'message': 'Only pending reservations can be cancelled'}, status=400)

        reservation.status = 'Cancelled'
        reservation.save()

        Notification.objects.create(
            user=request.user,
            message=f"Reservation #{reservation.id} has been cancelled."
        )

        return JsonResponse({'status': 'success', 'message': 'Reservation cancelled successfully'})
    except Reservation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Reservation not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Server error: {str(e)}'}, status=500)


@login_required
def get_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    notifications_data = [
        {
            'id': notif.id,
            'message': notif.message,
            'is_read': notif.is_read,
            'created_at': notif.created_at.isoformat()
        }
        for notif in notifications
    ]
    return JsonResponse({'status': 'success', 'notifications': notifications_data})


@login_required
def add_notification(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message')
        Notification.objects.create(user=request.user, message=message)
        return JsonResponse({'status': 'success', 'message': 'Notification added'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required
def mark_notification_read(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.is_read = True
            notification.save()
            return JsonResponse({'status': 'success', 'message': 'Notification marked as read'})
        except Notification.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Notification not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


def update_order_status(request, order_id, new_status):
    order = get_object_or_404(Order, id=order_id)
    order.status = new_status
    order.save()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'order_{order_id}',
        {
            'type': 'order_update',
            'status': new_status
        }
    )
    return JsonResponse({'status': 'success', 'message': f'Order {order_id} updated to {new_status}'})



@login_required
def get_rewards(request):
    user_reward, created = UserReward.objects.get_or_create(user=request.user)
    rewards = Reward.objects.all()
    rewards_data = [
        {
            'id': reward.id,  
            'name': reward.name,
            'points_required': reward.points_required,
            'description': reward.description
        }
        for reward in rewards
    ]
    return JsonResponse({
        'status': 'success',
        'points': user_reward.points,
        'rewards': rewards_data
    })
    

# Add points to the user's account
@login_required
@csrf_protect
def add_reward_points(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            points = data.get('points', 0)
            
            # Validate points
            if not isinstance(points, (int, float)) or points <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid points value. Must be a positive number.'
                }, status=400)

            user_reward, created = UserReward.objects.get_or_create(user=request.user)
            user_reward.points += int(points)
            user_reward.save()
            return JsonResponse({
                'status': 'success',
                'message': f'Added {points} points successfully'
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)


# Redeem a reward
@login_required
@csrf_protect
def redeem_reward(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reward_id = data.get('reward_id')

            # Ensure reward_id is a valid integer
            try:
                reward_id = int(reward_id)
            except (ValueError, TypeError):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid reward ID'
                }, status=400)

            user_reward, created = UserReward.objects.get_or_create(user=request.user)

            try:
                reward = Reward.objects.get(id=reward_id)
            except Reward.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Reward not found'
                }, status=404)

            # Check if user has enough points
            if user_reward.points < reward.points_required:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Not enough points. You need {reward.points_required - user_reward.points} more points.'
                }, status=400)

            # Deduct points
            user_reward.points -= reward.points_required
            user_reward.save()

            RedeemedReward.objects.create(
                user=request.user,
                reward=reward,
                points_spent=reward.points_required
            )

            return JsonResponse({
                'status': 'success',
                'message': f'Successfully redeemed {reward.name}'
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)


@login_required
def submit_support_request(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        subject = data.get('subject')
        message = data.get('message')

        SupportRequest.objects.create(
            user=request.user,
            subject=subject,
            message=message,
            status='Pending'
        )
        return JsonResponse({'status': 'success', 'message': 'Support request submitted'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required
def edit_profile(request):
    if request.method == 'POST':
        user = request.user

        # Ensure the user has a Profile object
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=user)

        # Get form data
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        location = request.POST.get('location')
        photo = request.FILES.get('photo')

        # Validate email
        errors = {}
        if not email:
            errors['email'] = 'Email is required'
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors['email'] = 'Valid email is required'

        # Validate phone (optional, but if provided, should be valid)
        if phone and (not phone.isdigit() or len(phone) < 10):
            errors['phone'] = 'Valid phone number is required (at least 10 digits)'

        # Validate photo size (optional, e.g., max 5MB)
        if photo and photo.size > 5 * 1024 * 1024:  # 5MB limit
            errors['photo'] = 'Photo size must be less than 5MB'

        if errors:
            return JsonResponse({'status': 'error', 'message': 'Validation failed', 'errors': errors})

        # Update user and profile
        try:
            user.email = email
            user.save()

            profile.phone = phone if phone else ''
            profile.location = location if location else ''
            if photo:
                profile.photo = photo
            profile.save()

            return JsonResponse({'status': 'success', 'message': 'Profile updated successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error saving profile: {str(e)}'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required
def submit_order(request):
    if request.method == 'POST':
        try:
            cart_items = CartItem.objects.filter(user=request.user)
            
            if not cart_items:
                return JsonResponse({'status': 'error', 'message': 'Cart is empty'})
            total = sum(item.total_price() for item in cart_items)
            
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    total=total,
                    status='Pending'
                )
                for cart_item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        dish=cart_item.dish,
                        quantity=cart_item.quantity,
                        price=cart_item.dish.price
                    )

                cart_items.delete()

            return JsonResponse({'status': 'success', 'message': 'Order submitted successfully', 'order_id': order.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


def logout_view(request):
    logout(request)
    return redirect('home') 
