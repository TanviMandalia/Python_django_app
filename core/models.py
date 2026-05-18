from django.db import models
from django.contrib.auth.models import User

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    SERVICE_CHOICES = [
        ('orthopedic', 'Orthopedic Therapy'),
        ('neurological', 'Neurological Rehab'),
        ('sports', 'Sports Rehabilitation'),
        ('pediatric', 'Pediatric Therapy'),
        ('womens', "Women's Health"),
        ('home_visit', 'Home Visit'),
    ]
    TIME_CHOICES = [
        ('09:00', '9:00 AM'), ('10:00', '10:00 AM'),
        ('11:00', '11:00 AM'), ('12:00', '12:00 PM'),
        ('14:00', '2:00 PM'), ('15:00', '3:00 PM'),
        ('16:00', '4:00 PM'), ('17:00', '5:00 PM'),
    ]
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    date = models.DateField()
    time = models.CharField(max_length=10, choices=TIME_CHOICES)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.username} - {self.service} - {self.date}"

    class Meta:
        ordering = ['-created_at']


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.content[:30]}"

    class Meta:
        ordering = ['created_at']