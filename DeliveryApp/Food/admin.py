from django.contrib import admin
from .models import  Dish, Cart, PasswordReset, Category, Order, OrderItem,Profile, Customer, Reservation,SupportRequest,RedeemedReward,UserReward,Reward,Notification,Favorite,User

admin.site.register(User) 
admin.site.register(Dish) 
admin.site.register(Cart)
admin.site.register(PasswordReset)
admin.site.register(Category)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Customer)
admin.site.register(Reservation)
admin.site.register(SupportRequest)
admin.site.register(RedeemedReward)
admin.site.register(UserReward)
admin.site.register(Reward)
admin.site.register(Notification)
admin.site.register(Favorite)
admin.site.register(Profile)


