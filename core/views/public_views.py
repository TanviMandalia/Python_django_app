from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from core.models import Blog, Review, ClinicSettings


def home(request):
    approved_reviews = Review.objects.filter(is_approved=True).order_by("-created_at")[:8]
    blogs = Blog.objects.order_by("-created_at")[:3]
    clinic_info = ClinicSettings.objects.first()
    return render(
        request,
        "public/home.html",
        {
            "approved_reviews": approved_reviews,
            "blogs": blogs,
            "clinic_info": clinic_info,
        },
    )


def about(request):
    clinic_info = ClinicSettings.objects.first()
    return render(request, "public/about.html", {"clinic_info": clinic_info})


def services(request):
    clinic_info = ClinicSettings.objects.first()
    return render(request, "public/services.html", {"clinic_info": clinic_info})


def contact(request):
    clinic_info = ClinicSettings.objects.first()
    if request.method == "POST":
        name = request.POST.get("name", "")
        email = request.POST.get("email", "")
        phone = request.POST.get("phone", "")
        message = request.POST.get("message", "")
        messages.success(request, "✅ Thank you! Your message has been received. Our team will contact you shortly.")
        return redirect("contact")
    return render(request, "public/contact.html", {"clinic_info": clinic_info})


def blog_list(request):
    category = request.GET.get("category", "")
    blogs = Blog.objects.order_by("-created_at")
    if category:
        blogs = blogs.filter(category=category)
    categories = Blog.CATEGORY_CHOICES
    return render(
        request,
        "public/blog.html",
        {"blogs": blogs, "categories": categories, "active_category": category},
    )


def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    recent_blogs = Blog.objects.exclude(id=blog.id).order_by("-created_at")[:3]
    return render(request, "public/blog_detail.html", {"blog": blog, "recent_blogs": recent_blogs})
