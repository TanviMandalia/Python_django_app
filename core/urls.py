from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login', views.login_view, name='login'),
    path('register', views.register_view, name='register'),
    path('logout', views.logout_view, name='logout'),
    path('client-dashboard', views.client_dashboard, name='client_dashboard'),
    path('admin-dashboard', views.admin_dashboard, name='admin_dashboard'),
    path('book', views.book_appointment, name='book_appointment'),
    path('my-appointments', views.my_appointments, name='my_appointments'),
    path('admin-appointments', views.admin_appointments, name='admin_appointments'),
    path('update-appointment/<int:appt_id>/<str:status>', views.update_appointment, name='update_appointment'),
    path('admin-patients', views.admin_patients, name='admin_patients'),
    path('chat', views.client_chat, name='client_chat'),
    path('admin-chat', views.admin_chat, name='admin_chat'),
    path('admin-chat/<int:patient_id>', views.admin_chat_detail, name='admin_chat_detail'),
]