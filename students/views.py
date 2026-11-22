"""Контроллеры приложения «Факультативы».

Страницы:

* :func:`home` — сводка по системе;
* :func:`students_list` / :func:`student_detail` — студенты и карточка
  студента с его факультативами, оценками и итоговой оценкой;
* :func:`electives_list` / :func:`elective_detail` — факультативы и их
  учебный план по семестрам;
* :func:`grades_list` / :func:`grade_create` — оценки и их выставление;
* :func:`requirements` — определение факультативов: кто набрал
  минимальный объём часов, кому и что нужно добрать;
* :func:`enroll` / :func:`unenroll` — запись на факультатив и отказ от неё;
* :func:`student_create` — добавление студента через web-форму;
* :func:`register`, :func:`login_view`, :func:`logout_view` — авторизация.
"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import GradeForm, StudentForm
from .models import (
    Elective,
    ElectiveSemester,
    Enrollment,
    Grade,
    Student,
    final_grade,
    final_grades_map,
    minimum_required_hours,
)
from .progress import build_progress, plan_totals, recommend_electives


def redirect_back(request, fallback):
    """Вернуть пользователя на предыдущую страницу безопасным способом."""

    referer = request.META.get("HTTP_REFERER")

    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)

    return redirect(fallback)


def sync_enrollment_status(student, elective):
    """Обновить статус записи по итоговой оценке за факультатив.

    Если у студента есть зачтённая итоговая оценка, запись считается
    завершённой; иначе студент продолжает обучение.
    """

    enrollment = Enrollment.objects.filter(
        student=student, elective=elective
    ).first()

    if enrollment is None or enrollment.is_cancelled:
        return

    last = final_grade(student, elective)

    new_status = (
        Enrollment.STATUS_COMPLETED
        if last is not None and last.is_passing
        else Enrollment.STATUS_ACTIVE
    )

    if enrollment.status != new_status:
        enrollment.status = new_status
        enrollment.save(update_fields=["status"])


def home(request):
    """Главная страница: сводка по студентам, факультативам и оценкам."""

    students = list(Student.objects.all())
    progress = build_progress(students)

    electives = Elective.objects.filter(is_active=True).prefetch_related(
        "semesters", "enrollments", "teacher"
    )

    last_grades = (
        Grade.objects.select_related(
            "student", "elective_semester__elective"
        )
        .order_by("-exam_date", "-id")[:4]
    )

    context = {
        "students_count": len(students),
        "electives_count": len(electives),
        "semesters_count": ElectiveSemester.objects.count(),
        "enrollments_count": Enrollment.objects.exclude(
            status=Enrollment.STATUS_CANCELLED
        ).count(),
        "grades_count": Grade.objects.count(),
        "required_hours": minimum_required_hours(),
        "met_count": sum(1 for item in progress.values() if item.is_met),
        "plan": plan_totals(),
        "electives": electives,
        "last_grades": last_grades,
        "progress_rows": [
            {"student": item.student, "progress": item}
            for item in progress.values()
        ],
    }

    return render(request, "students/home.html", context)


def students_list(request):
    """Список студентов с поиском, фильтром по группе и прогрессом."""

    query = request.GET.get("q", "").strip()
    group = request.GET.get("group", "").strip()

    students = Student.objects.all()

    if query:
        students = students.filter(
            Q(last_name__icontains=query)
            | Q(first_name__icontains=query)
            | Q(patronymic__icontains=query)
            | Q(group__icontains=query)
            | Q(phone__icontains=query)
        )

    if group:
        students = students.filter(group=group)

    students = list(students)
    progress = build_progress(students)

    context = {
        "rows": [
            {"student": student, "progress": progress[student.pk]}
            for student in students
        ],
        "groups": list(
            Student.objects.order_by("group")
            .values_list("group", flat=True)
            .distinct()
        ),
        "query": query,
        "group": group,
        "required_hours": minimum_required_hours(),
    }

    return render(request, "students/students.html", context)


def student_detail(request, pk):
    """Карточка студента: анкета, факультативы, оценки, рекомендации."""

    student = get_object_or_404(Student, pk=pk)

    enrollments = list(
        student.enrollments.exclude(status=Enrollment.STATUS_CANCELLED)
        .select_related("elective")
        .prefetch_related("elective__semesters")
    )

    grades = list(
        student.grades.select_related("elective_semester__elective").order_by(
            "exam_date", "id"
        )
    )

    finals = {}
    history = {}

    for grade in grades:
        elective_id = grade.elective_semester.elective_id
        finals[elective_id] = grade
        history.setdefault(elective_id, []).append(grade)

    rows = [
        {
            "enrollment": enrollment,
            "elective": enrollment.elective,
            "hours": enrollment.elective.total_hours,
            "final": finals.get(enrollment.elective_id),
            "history": history.get(enrollment.elective_id, []),
        }
        for enrollment in enrollments
    ]

    progress = build_progress([student])[student.pk]

    context = {
        "student": student,
        "rows": rows,
        "progress": progress,
        "required_hours": minimum_required_hours(),
        "recommendations": recommend_electives(progress, limit=4),
    }

    return render(request, "students/student_detail.html", context)


@login_required
def student_create(request):
    """Добавление студента через web-форму."""

    if request.method == "POST":
        form = StudentForm(request.POST)

        if form.is_valid():
            student = form.save()
            messages.success(
                request, f"Студент «{student.full_name}» добавлен."
            )
            return redirect("student_detail", pk=student.pk)
    else:
        form = StudentForm()

    return render(request, "students/student_form.html", {"form": form})


def electives_list(request):
    """Каталог факультативов с поиском по названию и преподавателю."""

    query = request.GET.get("q", "").strip()

    electives = Elective.objects.prefetch_related(
        "semesters", "enrollments", "teacher"
    )

    if query:
        electives = electives.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(teacher__last_name__icontains=query)
        )

    context = {
        "electives": electives,
        "query": query,
        "required_hours": minimum_required_hours(),
    }

    return render(request, "students/electives.html", context)


def elective_detail(request, elective_id):
    """Страница факультатива: учебный план, студенты и их итоговые оценки."""

    elective = get_object_or_404(
        Elective.objects.prefetch_related(
            "semesters", "enrollments__student"
        ),
        pk=elective_id,
    )

    enrollments = [
        enrollment
        for enrollment in elective.enrollments.all()
        if not enrollment.is_cancelled
    ]
    enrollments.sort(key=lambda item: item.student.full_name)

    finals = final_grades_map(elective_id=elective.pk)

    rows = [
        {
            "enrollment": enrollment,
            "student": enrollment.student,
            "final": finals.get((enrollment.student_id, elective.pk)),
        }
        for enrollment in enrollments
    ]

    enrolled_ids = [enrollment.student_id for enrollment in enrollments]

    available_students = Student.objects.exclude(pk__in=enrolled_ids)

    context = {
        "elective": elective,
        "rows": rows,
        "available_students": available_students,
        "required_hours": minimum_required_hours(),
    }

    return render(request, "students/elective_detail.html", context)


@login_required
@require_POST
def enroll(request):
    """Записать студента на факультатив."""

    student = get_object_or_404(Student, pk=request.POST.get("student_id"))
    elective = get_object_or_404(Elective, pk=request.POST.get("elective_id"))
    fallback = reverse("elective_detail", args=[elective.pk])

    if not elective.is_active:
        messages.error(
            request, f"Набор на факультатив «{elective.name}» закрыт."
        )
        return redirect_back(request, fallback)

    enrollment, created = Enrollment.objects.get_or_create(
        student=student, elective=elective
    )

    if created:
        messages.success(
            request,
            f"{student.short_name} записан(а) на «{elective.name}».",
        )
    elif enrollment.is_cancelled:
        enrollment.status = Enrollment.STATUS_ACTIVE
        enrollment.save(update_fields=["status"])
        messages.success(request, "Запись возобновлена.")
    else:
        messages.info(
            request,
            f"{student.short_name} уже записан(а) на «{elective.name}».",
        )

    sync_enrollment_status(student, elective)

    return redirect_back(request, fallback)


@login_required
@require_POST
def unenroll(request):
    """Отменить запись студента на факультатив."""

    enrollment = get_object_or_404(
        Enrollment.objects.select_related("student", "elective"),
        pk=request.POST.get("enrollment_id"),
    )
    fallback = reverse("student_detail", args=[enrollment.student_id])

    enrollment.status = Enrollment.STATUS_CANCELLED
    enrollment.save(update_fields=["status"])

    messages.success(
        request,
        f"Запись на «{enrollment.elective.name}» отменена.",
    )

    return redirect_back(request, fallback)


def grades_list(request):
    """Итоговые оценки по предметам и полная история экзаменов."""

    enrollments = (
        Enrollment.objects.exclude(status=Enrollment.STATUS_CANCELLED)
        .select_related("student", "elective")
        .prefetch_related("elective__semesters")
    )

    finals = final_grades_map()

    rows = [
        {
            "enrollment": enrollment,
            "student": enrollment.student,
            "elective": enrollment.elective,
            "final": finals.get((enrollment.student_id, enrollment.elective_id)),
        }
        for enrollment in enrollments
    ]

    rows.sort(
        key=lambda row: (
            row["student"].last_name,
            row["student"].first_name,
            row["elective"].name,
        )
    )

    context = {
        "rows": rows,
        "grades": Grade.objects.select_related(
            "student", "elective_semester__elective"
        ),
        "required_hours": minimum_required_hours(),
    }

    return render(request, "students/grades.html", context)


@login_required
def grade_create(request, student_id=None):
    """Выставить оценку студенту (форма с проверками)."""

    student = (
        get_object_or_404(Student, pk=student_id)
        if student_id is not None
        else None
    )

    if request.method == "POST":
        form = GradeForm(request.POST, student=student)

        if form.is_valid():
            grade = form.save()

            sync_enrollment_status(grade.student, grade.elective)

            messages.success(
                request,
                f"Оценка {grade.grade} по предмету "
                f"«{grade.elective.name}» сохранена.",
            )

            return redirect("student_detail", pk=grade.student_id)
    else:
        form = GradeForm(student=student)

    return render(
        request,
        "students/grade_form.html",
        {"form": form, "student": student},
    )


def requirements(request):
    """Определение факультативов: выполнение минимального объёма часов."""

    students = list(Student.objects.prefetch_related("enrollments__elective"))
    progress = build_progress(students)

    rows = [
        {"student": student, "progress": progress[student.pk]}
        for student in students
    ]

    rows.sort(
        key=lambda row: (
            row["progress"].is_met,
            -row["progress"].shortfall_hours,
            row["student"].last_name,
        )
    )

    context = {
        "rows": rows,
        "required_hours": minimum_required_hours(),
        "met_count": sum(1 for row in rows if row["progress"].is_met),
        "short_count": sum(1 for row in rows if not row["progress"].is_met),
    }

    return render(request, "students/requirements.html", context)


def register(request):
    """Регистрация нового пользователя системы."""

    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        form = {
            "username": username,
        }

        if not username or not password or not password2:
            form["error"] = "Заполните все поля."
        elif len(username) < 3:
            form["error"] = "Логин должен содержать не менее 3 символов."
        elif len(password) < 6:
            form["error"] = "Пароль должен содержать не менее 6 символов."
        elif password != password2:
            form["error"] = "Пароли не совпадают."
        elif User.objects.filter(username=username).exists():
            form["error"] = "Пользователь с таким логином уже существует."

        if "error" not in form:
            user = User.objects.create_user(
                username=username, password=password
            )

            login(request, user)

            messages.success(
                request, f"Добро пожаловать, {user.username}!"
            )

            return redirect("home")

        return render(request, "students/register.html", {"form": form})

    return render(request, "students/register.html")


def login_view(request):
    """Вход в систему."""

    if request.user.is_authenticated:
        return redirect("home")

    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            return render(
                request,
                "students/login.html",
                {
                    "error": "Заполните все поля.",
                    "next": next_url,
                },
            )

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            messages.success(
                request, f"Вы вошли как {user.username}."
            )

            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            return redirect("home")

        return render(
            request,
            "students/login.html",
            {
                "error": "Неверный логин или пароль.",
                "next": next_url,
            },
        )

    return render(request, "students/login.html", {"next": next_url})


def logout_view(request):
    """Выход из системы."""

    logout(request)
    messages.info(request, "Вы вышли из системы.")

    return redirect("home")

