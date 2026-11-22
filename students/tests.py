"""Тесты приложения «Факультативы».

Проверяются модели, расчёт минимального объёма часов, итоговая оценка,
запись на факультативы, выставление оценок и авторизация.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import GradeForm, StudentForm
from .models import (
    Elective,
    ElectiveSemester,
    Enrollment,
    Grade,
    Student,
    Teacher,
    final_grade,
    final_grades_map,
    minimum_required_hours,
)
from .progress import build_progress, plan_totals, recommend_electives


class BaseDataMixin:
    """Общий набор данных: преподаватель, факультативы и студент."""

    def create_data(self):
        self.teacher = Teacher.objects.create(
            last_name="Смирнов",
            first_name="Пётр",
            patronymic="Андреевич",
            position="доцент",
        )

        self.python = Elective.objects.create(
            name="Python для начинающих",
            description="Базовый курс программирования.",
            teacher=self.teacher,
        )

        self.python_first = ElectiveSemester.objects.create(
            elective=self.python,
            academic_year="2026/2027",
            semester_number=1,
            lecture_hours=32,
            practice_hours=16,
            laboratory_hours=16,
        )

        self.python_second = ElectiveSemester.objects.create(
            elective=self.python,
            academic_year="2026/2027",
            semester_number=2,
            lecture_hours=32,
            practice_hours=16,
            laboratory_hours=16,
        )

        self.web = Elective.objects.create(
            name="Web-разработка",
            description="Веб-приложения на Django.",
            teacher=self.teacher,
        )

        self.web_first = ElectiveSemester.objects.create(
            elective=self.web,
            academic_year="2026/2027",
            semester_number=1,
            lecture_hours=32,
            practice_hours=16,
            laboratory_hours=12,
        )

        self.student = Student.objects.create(
            last_name="Иванов",
            first_name="Иван",
            patronymic="Иванович",
            group="СТ-25",
            address="ул. Ленина, 10",
            phone="+7 900 111-22-33",
        )

        self.user = User.objects.create_user(
            username="tester", password="secret123"
        )


class ModelTests(BaseDataMixin, TestCase):
    """Модели: ФИО, объём часов, итоговая оценка."""

    def setUp(self):
        self.create_data()

    def test_student_full_name(self):
        self.assertEqual(
            self.student.full_name, "Иванов Иван Иванович"
        )
        self.assertEqual(self.student.short_name, "Иванов И.И.")

    def test_semester_total_hours(self):
        self.assertEqual(self.python_first.total_hours, 64)

    def test_elective_total_hours(self):
        self.assertEqual(self.python.total_hours, 128)
        self.assertEqual(self.web.total_hours, 60)

    def test_elective_duration(self):
        self.assertEqual(self.python.duration_semesters, 2)
        self.assertTrue(self.python.is_multisemester)
        self.assertFalse(self.web.is_multisemester)

    def test_hours_by_type(self):
        hours = self.python.hours_by_type

        self.assertEqual(hours["lectures"], 64)
        self.assertEqual(hours["practice"], 32)
        self.assertEqual(hours["laboratory"], 32)

    def test_final_grade_is_last_by_exam_date(self):
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=4,
            exam_date=date(2026, 1, 15),
        )
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_second,
            grade=5,
            exam_date=date(2026, 6, 10),
        )

        self.assertEqual(
            final_grade(self.student, self.python).grade, 5
        )

    def test_final_grade_ignores_creation_order(self):
        # Поздняя по дате оценка создана первой: итоговой всё равно
        # должна стать она, а не последняя добавленная запись.
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_second,
            grade=5,
            exam_date=date(2026, 6, 10),
        )
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=3,
            exam_date=date(2026, 1, 15),
        )

        self.assertEqual(
            final_grade(self.student, self.python).grade, 5
        )

    def test_final_grades_map(self):
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=4,
            exam_date=date(2026, 1, 15),
        )
        Grade.objects.create(
            student=self.student,
            elective_semester=self.web_first,
            grade=5,
            exam_date=date(2026, 1, 20),
        )

        finals = final_grades_map(student_ids=[self.student.pk])

        self.assertEqual(finals[(self.student.pk, self.python.pk)].grade, 4)
        self.assertEqual(finals[(self.student.pk, self.web.pk)].grade, 5)

    def test_grade_passing(self):
        grade = Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=3,
            exam_date=date(2026, 1, 15),
        )

        self.assertTrue(grade.is_passing)
        self.assertEqual(grade.elective, self.python)
        self.assertEqual(grade.exam_date_label, "15.01.2026")

    def test_enrollment_status_label(self):
        enrollment = Enrollment.objects.create(
            student=self.student, elective=self.python
        )

        self.assertEqual(enrollment.status_label, "Обучается")
        self.assertFalse(enrollment.is_cancelled)
        self.assertIn("Иванов", str(enrollment))

    def test_enrollment_is_unique(self):
        Enrollment.objects.create(
            student=self.student, elective=self.python
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(
                    student=self.student, elective=self.python
                )

    def test_minimum_required_hours_from_settings(self):
        self.assertEqual(minimum_required_hours(), 128)

    def test_plan_totals(self):
        plan = plan_totals()

        self.assertEqual(plan["lectures"], 96)
        self.assertEqual(plan["total"], 188)
        self.assertLessEqual(plan["lecture_width"], 100)


@override_settings(MIN_ELECTIVE_HOURS=100)
class ProgressTests(BaseDataMixin, TestCase):
    """Минимальный объём часов: зачёт, план и подбор факультативов."""

    def setUp(self):
        self.create_data()
        Enrollment.objects.create(
            student=self.student, elective=self.python
        )

    def test_no_grades_means_zero_credited_hours(self):
        progress = build_progress([self.student])[self.student.pk]

        self.assertEqual(progress.credited_hours, 0)
        self.assertEqual(progress.planned_hours, 128)
        self.assertFalse(progress.is_met)
        self.assertEqual(progress.shortfall_hours, 100)

    def test_passed_semesters_are_credited(self):
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=4,
            exam_date=date(2026, 1, 15),
        )

        progress = build_progress([self.student])[self.student.pk]

        self.assertEqual(progress.credited_hours, 64)
        self.assertEqual(progress.planned_hours, 64)
        self.assertEqual(progress.passed_electives, 1)
        self.assertEqual(progress.percent, 64)

    def test_failed_grade_is_not_credited(self):
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=2,
            exam_date=date(2026, 1, 15),
        )

        progress = build_progress([self.student])[self.student.pk]

        self.assertEqual(progress.credited_hours, 0)
        self.assertFalse(progress.is_met)

    def test_minimum_is_met(self):
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=5,
            exam_date=date(2026, 1, 15),
        )
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_second,
            grade=5,
            exam_date=date(2026, 6, 10),
        )

        progress = build_progress([self.student])[self.student.pk]

        self.assertTrue(progress.is_met)
        self.assertEqual(progress.credited_hours, 128)
        self.assertEqual(progress.shortfall_hours, 0)
        self.assertEqual(progress.status_label, "Минимум выполнен")
        self.assertEqual(progress.status_css, "success")

    def test_cancelled_enrollment_is_ignored(self):
        Enrollment.objects.filter(student=self.student).update(
            status=Enrollment.STATUS_CANCELLED
        )

        progress = build_progress([self.student])[self.student.pk]

        self.assertEqual(progress.planned_hours, 0)
        self.assertEqual(progress.enrolled_electives, 0)

    def test_grades_of_cancelled_enrollment_are_not_credited(self):
        Grade.objects.create(
            student=self.student,
            elective_semester=self.python_first,
            grade=5,
            exam_date=date(2026, 1, 15),
        )

        Enrollment.objects.filter(student=self.student).update(
            status=Enrollment.STATUS_CANCELLED
        )

        progress = build_progress([self.student])[self.student.pk]

        self.assertEqual(progress.credited_hours, 0)
        self.assertEqual(progress.passed_electives, 0)
        self.assertFalse(progress.is_met)

    def test_recommendations_skip_enrolled_electives(self):
        progress = build_progress([self.student])[self.student.pk]
        rows = recommend_electives(progress)

        names = [row["elective"].name for row in rows]

        self.assertNotIn(self.python.name, names)
        self.assertIn(self.web.name, names)

    def test_recommendations_prefer_covering_elective(self):
        # Не хватает 100 часов: Web (60) не закрывает минимум,
        # а «Анализ данных» объёмом 120 — закрывает.
        analysis = Elective.objects.create(name="Анализ данных")
        ElectiveSemester.objects.create(
            elective=analysis,
            academic_year="2026/2027",
            semester_number=1,
            lecture_hours=60,
            practice_hours=40,
            laboratory_hours=20,
        )

        progress = build_progress([self.student])[self.student.pk]
        rows = recommend_electives(progress)

        self.assertEqual(rows[0]["elective"], analysis)
        self.assertTrue(rows[0]["covers"])
        self.assertFalse(rows[1]["covers"])


class ViewTests(BaseDataMixin, TestCase):
    """Страницы, запись на факультативы и выставление оценок."""

    def setUp(self):
        self.create_data()
        self.client.force_login(self.user)

    def test_pages_are_available(self):
        for name in (
            "home",
            "students",
            "electives",
            "grades",
            "requirements",
            "student_create",
            "grade_create",
        ):
            response = self.client.get(reverse(name))

            self.assertEqual(
                response.status_code,
                200,
                msg=f"Страница {name} недоступна",
            )

    def test_guest_auth_pages_are_available(self):
        self.client.logout()

        for name in ("login", "register"):
            response = self.client.get(reverse(name))

            self.assertEqual(
                response.status_code,
                200,
                msg=f"Страница {name} недоступна",
            )

    def test_authenticated_user_is_redirected_from_auth_pages(self):
        for name in ("login", "register"):
            response = self.client.get(reverse(name))

            self.assertEqual(response.status_code, 302)

    def test_student_detail_page(self):
        response = self.client.get(
            reverse("student_detail", args=[self.student.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Иванов")
        self.assertContains(response, "СТ-25")

    def test_elective_detail_page(self):
        response = self.client.get(
            reverse("elective_detail", args=[self.python.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python для начинающих")
        self.assertContains(response, "2026/2027")
        self.assertContains(response, "Лекции")

    def test_students_search(self):
        Student.objects.create(
            last_name="Петров",
            first_name="Алексей",
            group="ИС-24",
            address="ул. Гагарина, 15",
            phone="+7 900 222-33-44",
        )

        response = self.client.get(reverse("students"), {"q": "Петров"})

        self.assertContains(response, "Петров")
        self.assertNotContains(response, "Иванов")

    def test_students_group_filter(self):
        Student.objects.create(
            last_name="Петров",
            first_name="Алексей",
            group="ИС-24",
            address="ул. Гагарина, 15",
            phone="+7 900 222-33-44",
        )

        response = self.client.get(reverse("students"), {"group": "СТ-25"})

        self.assertContains(response, "Иванов")
        self.assertNotContains(response, "Петров")

    def test_electives_search(self):
        response = self.client.get(reverse("electives"), {"q": "Web"})

        self.assertContains(response, "Web-разработка")
        self.assertNotContains(response, "Python для начинающих")

    def test_enroll_creates_record(self):
        response = self.client.post(
            reverse("enroll"),
            {"student_id": self.student.pk, "elective_id": self.web.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Enrollment.objects.filter(
                student=self.student, elective=self.web
            ).exists()
        )

    def test_enroll_reactivates_cancelled_record(self):
        Enrollment.objects.create(
            student=self.student,
            elective=self.web,
            status=Enrollment.STATUS_CANCELLED,
        )

        self.client.post(
            reverse("enroll"),
            {"student_id": self.student.pk, "elective_id": self.web.pk},
        )

        enrollment = Enrollment.objects.get(
            student=self.student, elective=self.web
        )

        self.assertEqual(enrollment.status, Enrollment.STATUS_ACTIVE)

    def test_enroll_requires_login(self):
        self.client.logout()

        response = self.client.post(
            reverse("enroll"),
            {"student_id": self.student.pk, "elective_id": self.web.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertFalse(
            Enrollment.objects.filter(
                student=self.student, elective=self.web
            ).exists()
        )

    def test_enroll_closed_elective(self):
        Elective.objects.filter(pk=self.web.pk).update(is_active=False)

        response = self.client.post(
            reverse("enroll"),
            {"student_id": self.student.pk, "elective_id": self.web.pk},
            follow=True,
        )

        self.assertContains(response, "Набор на факультатив")
        self.assertFalse(
            Enrollment.objects.filter(
                student=self.student, elective=self.web
            ).exists()
        )

    def test_unenroll_cancels_record(self):
        enrollment = Enrollment.objects.create(
            student=self.student, elective=self.python
        )

        response = self.client.post(
            reverse("unenroll"), {"enrollment_id": enrollment.pk}
        )

        self.assertEqual(response.status_code, 302)

        enrollment.refresh_from_db()

        self.assertEqual(enrollment.status, Enrollment.STATUS_CANCELLED)

    def test_grade_create_valid(self):
        Enrollment.objects.create(
            student=self.student, elective=self.python
        )

        response = self.client.post(
            reverse("student_grade_create", args=[self.student.pk]),
            {
                "elective_semester": self.python_first.pk,
                "grade": 5,
                "exam_date": "2026-01-15",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Grade.objects.filter(
                student=self.student,
                elective_semester=self.python_first,
                grade=5,
            ).exists()
        )

        enrollment = Enrollment.objects.get(
            student=self.student, elective=self.python
        )

        self.assertEqual(enrollment.status, Enrollment.STATUS_COMPLETED)

    def test_grade_requires_enrollment(self):
        response = self.client.post(
            reverse("student_grade_create", args=[self.student.pk]),
            {
                "elective_semester": self.web_first.pk,
                "grade": 5,
                "exam_date": "2026-01-15",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Grade.objects.count(), 0)

    def test_grade_form_explains_missing_enrollment(self):
        # Общая форма позволяет выбрать любой семестр, но при сохранении
        # проверяет, что студент записан на этот факультатив.
        response = self.client.post(
            reverse("grade_create"),
            {
                "student": self.student.pk,
                "elective_semester": self.web_first.pk,
                "grade": 5,
                "exam_date": "2026-01-15",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не записан")
        self.assertEqual(Grade.objects.count(), 0)

    def test_grade_future_date_is_rejected(self):
        Enrollment.objects.create(
            student=self.student, elective=self.python
        )

        tomorrow = timezone.localdate() + timedelta(days=1)

        response = self.client.post(
            reverse("student_grade_create", args=[self.student.pk]),
            {
                "elective_semester": self.python_first.pk,
                "grade": 4,
                "exam_date": tomorrow.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не может быть в будущем")
        self.assertEqual(Grade.objects.count(), 0)

    def test_grade_create_requires_login(self):
        self.client.logout()

        response = self.client.post(
            reverse("grade_create"),
            {
                "student": self.student.pk,
                "elective_semester": self.python_first.pk,
                "grade": 5,
                "exam_date": "2026-01-15",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Grade.objects.count(), 0)

    def test_student_create(self):
        response = self.client.post(
            reverse("student_create"),
            {
                "last_name": "петров",
                "first_name": "алексей",
                "patronymic": "сергеевич",
                "group": "ис-24",
                "address": "ул. Гагарина, 15",
                "phone": "+7 900 222-33-44",
            },
        )

        self.assertEqual(response.status_code, 302)

        student = Student.objects.get(last_name="Петров")

        self.assertEqual(student.first_name, "Алексей")
        self.assertEqual(student.group, "ИС-24")

    def test_student_create_rejects_short_phone(self):
        response = self.client.post(
            reverse("student_create"),
            {
                "last_name": "Сидоров",
                "first_name": "Пётр",
                "patronymic": "",
                "group": "СТ-25",
                "address": "ул. Мира, 1",
                "phone": "123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не менее 10 цифр")
        self.assertEqual(Student.objects.count(), 1)

    def test_student_create_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("student_create"))

        self.assertEqual(response.status_code, 302)

    def test_requirements_page_shows_student(self):
        response = self.client.get(reverse("requirements"))

        self.assertContains(response, "Иванов")
        self.assertContains(response, "Минимальный объём часов")


class FormTests(BaseDataMixin, TestCase):
    """Формы: нормализация анкеты и проверки при выставлении оценки."""

    def setUp(self):
        self.create_data()

    def test_student_form_normalizes_values(self):
        form = StudentForm(
            data={
                "last_name": "  петров ",
                "first_name": "алексей",
                "patronymic": "сергеевич",
                "group": " ис-24 ",
                "address": "  ул. Гагарина, 15 ",
                "phone": "+7 900 222-33-44",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["last_name"], "Петров")
        self.assertEqual(form.cleaned_data["group"], "ИС-24")
        self.assertEqual(form.cleaned_data["address"], "ул. Гагарина, 15")

    def test_student_form_rejects_letters_in_phone(self):
        form = StudentForm(
            data={
                "last_name": "Петров",
                "first_name": "Алексей",
                "patronymic": "",
                "group": "ИС-24",
                "address": "ул. Гагарина, 15",
                "phone": "телефон",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_grade_form_limits_semesters_to_student_electives(self):
        Enrollment.objects.create(
            student=self.student, elective=self.python
        )

        form = GradeForm(student=self.student)

        self.assertNotIn("student", form.fields)
        self.assertEqual(
            list(form.fields["elective_semester"].queryset),
            [self.python_first, self.python_second],
        )

    def test_grade_form_rejects_elective_without_enrollment(self):
        form = GradeForm(
            data={
                "student": self.student.pk,
                "elective_semester": self.web_first.pk,
                "grade": 5,
                "exam_date": "2026-01-15",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("elective_semester", form.errors)

    def test_grade_form_accepts_enrolled_student(self):
        Enrollment.objects.create(
            student=self.student, elective=self.python
        )

        form = GradeForm(
            data={
                "student": self.student.pk,
                "elective_semester": self.python_first.pk,
                "grade": 4,
                "exam_date": "2026-01-15",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        grade = form.save()

        self.assertEqual(grade.student, self.student)
        self.assertEqual(grade.grade, 4)


class AdminTests(BaseDataMixin, TestCase):
    """Административная панель: все модели доступны администратору."""

    def setUp(self):
        self.create_data()

        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="secret123"
        )
        self.client.force_login(self.admin_user)

    def test_admin_index(self):
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def test_admin_changelists(self):
        urls = (
            "admin:students_teacher_changelist",
            "admin:students_student_changelist",
            "admin:students_elective_changelist",
            "admin:students_electivesemester_changelist",
            "admin:students_enrollment_changelist",
            "admin:students_grade_changelist",
        )

        for name in urls:
            response = self.client.get(reverse(name))

            self.assertEqual(
                response.status_code, 200, msg=f"Не открывается {name}"
            )

    def test_admin_add_forms(self):
        urls = (
            "admin:students_teacher_add",
            "admin:students_student_add",
            "admin:students_elective_add",
            "admin:students_grade_add",
        )

        for name in urls:
            response = self.client.get(reverse(name))

            self.assertEqual(
                response.status_code, 200, msg=f"Не открывается {name}"
            )

    def test_admin_requires_staff(self):
        self.client.logout()
        self.client.force_login(self.user)

        response = self.client.get(reverse("admin:index"))

        self.assertNotEqual(response.status_code, 200)


class AuthTests(BaseDataMixin, TestCase):
    """Регистрация, вход и выход."""

    def setUp(self):
        self.create_data()

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password": "secret123",
                "password2": "secret123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())

        response = self.client.get(reverse("home"))

        self.assertContains(response, "newuser")

    def test_register_password_mismatch(self):
        self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password": "secret123",
                "password2": "other123",
            },
        )

        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_register_short_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password": "123",
                "password2": "123",
            },
        )

        self.assertContains(response, "не менее 6 символов")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_login_success(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

    def test_login_failure(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")

    def test_logout(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Выйти")

    def test_guest_sees_login_links(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Регистрация")
        self.assertContains(response, "Войти")
