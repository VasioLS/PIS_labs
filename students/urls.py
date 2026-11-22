"""Маршруты приложения «Факультативы»."""

from django.urls import path

from . import views

urlpatterns = [
    # Главная страница.
    path("", views.home, name="home"),

    # Студенты.
    path("students/", views.students_list, name="students"),
    path("students/add/", views.student_create, name="student_create"),
    path("students/<int:pk>/", views.student_detail, name="student_detail"),
    path(
        "students/<int:student_id>/grade/",
        views.grade_create,
        name="student_grade_create",
    ),

    # Факультативы.
    path("electives/", views.electives_list, name="electives"),
    path(
        "electives/<int:elective_id>/",
        views.elective_detail,
        name="elective_detail",
    ),

    # Запись на факультативы.
    path("enroll/", views.enroll, name="enroll"),
    path("unenroll/", views.unenroll, name="unenroll"),

    # Оценки.
    path("grades/", views.grades_list, name="grades"),
    path("grades/add/", views.grade_create, name="grade_create"),

    # Определение факультативов по минимальному объёму часов.
    path("requirements/", views.requirements, name="requirements"),

    # Авторизация.
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
]
