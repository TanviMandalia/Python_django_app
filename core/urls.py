from django.urls import path
from . import views

urlpatterns = [
    # Public Pages
    path('', views.home, name='home'),
    path('about', views.about, name='about'),
    path('services', views.services, name='services'),
    path('contact', views.contact, name='contact'),
    path('blog', views.blog, name='blog'),
    # path('appointment-request',views.public_book_appointment,name='public_book_appointment'),

    # Auth
    path('login', views.login_view, name='login'),
    path('register', views.register_view, name='register'),
    path('logout', views.logout_view, name='logout'),

    # Client
    path('client-dashboard', views.client_dashboard, name='client_dashboard'),
    path('book', views.book_appointment, name='book_appointment'),
    path('my-appointments', views.my_appointments, name='my_appointments'),
    path('chat', views.client_chat, name='client_chat'),

    # Admin
    path('admin-dashboard', views.admin_dashboard, name='admin_dashboard'),
    path('admin-appointments', views.admin_appointments, name='admin_appointments'),
    path('update-appointment/<int:appt_id>/<str:status>', views.update_appointment, name='update_appointment'),
    path('admin-patients', views.admin_patients, name='admin_patients'),
    path('admin-chat', views.admin_chat, name='admin_chat'),
    path('admin-chat/<int:patient_id>', views.admin_chat_detail, name='admin_chat_detail'),

    # delete message
   path('delete-message/<int:message_id>/', views.delete_message, name='delete_message'),

    # Staff Management
    path('admin-staff', views.admin_staff, name='admin_staff'),
    path('add-staff', views.add_staff, name='add_staff'),
    path('admin-leaves', views.admin_leaves, name='admin_leaves'),
    path('update-leave/<int:leave_id>/<str:status>', views.update_leave, name='update_leave'),
    path('admin-attendance', views.admin_attendance, name='admin_attendance'),
    path('admin-salary', views.admin_salary, name='admin_salary'),
    path('admin-tasks', views.admin_tasks, name='admin_tasks'),
    path('add-task', views.add_task, name='add_task'),
    path('admin-session-notes', views.admin_session_notes, name='admin_session_notes'),

    # Staff Dashboard
    path('staff-dashboard', views.staff_dashboard, name='staff_dashboard'),
    path('staff-attendance', views.staff_attendance, name='staff_attendance'),
    path('staff-leave', views.staff_leave, name='staff_leave'),
    path('staff-salary', views.staff_salary, name='staff_salary'),
    path('staff-tasks', views.staff_tasks, name='staff_tasks'),
    path('update-task/<int:task_id>/<str:status>', views.update_task, name='update_task'),
    path('staff-session-notes', views.staff_session_notes, name='staff_session_notes'),
    path('add-session-note', views.add_session_note, name='add_session_note'),
]