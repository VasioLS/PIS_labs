"""Временные представления для съёмки скриншотов (удалить после работы)."""

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import redirect, render


def dev_login(request):
    """Войти суперпользователем и перейти на нужную страницу."""

    user = User.objects.filter(is_superuser=True).order_by("id").first()

    if user is None:
        user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin12345"
        )

    login(request, user)

    return redirect(request.GET.get("next", "/"))


def dev_preview(request):
    """Показать шаблон с нужным контекстом (для скриншотов состояний форм)."""

    template = request.GET.get("template", "students/login.html")
    allowed = {"students/login.html", "students/register.html"}

    if template not in allowed:
        template = "students/login.html"

    context = {
        "error": request.GET.get("error", ""),
        "form": {
            "error": request.GET.get("form_error", ""),
            "username": request.GET.get("username", ""),
        },
        "next": "",
    }

    return render(request, template, context)
