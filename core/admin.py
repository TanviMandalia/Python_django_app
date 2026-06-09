from django.contrib import admin
from .models import Blog

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'created_at')
    prepopulated_fields = {"slug": ("title",)}  # 🔥 auto fill in admin
    search_fields = ('title',)
    