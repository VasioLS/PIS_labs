"""Демонстрационные данные для системы «Факультативы».

Команда создаёт преподавателей, факультативы с учебным планом по семестрам,
студентов, записи на факультативы и оценки за экзамены. Данные подобраны
так, чтобы были видны все возможности системы:

* многoсеместровые факультативы;
* пересдача: у одного студента по одному предмету две оценки, итоговой
  становится последняя;
* студенты, выполнившие и не выполнившие минимальный объём часов;
* подбор факультативов для тех, кому нужно добрать часы.

Запуск::

    python manage.py seed_demo            # создать недостающее
    python manage.py seed_demo --reset    # удалить записи и оценки и создать заново
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from students.models import (
    Elective,
    ElectiveSemester,
    Enrollment,
    Grade,
    Student,
    Teacher,
)

ACADEMIC_YEAR_OLD = "2025/2026"
ACADEMIC_YEAR_NEW = "2026/2027"

TEACHERS = [
    {
        "last_name": "Смирнов",
        "first_name": "Пётр",
        "patronymic": "Андреевич",
        "position": "доцент",
        "email": "smirnov@example.edu",
    },
    {
        "last_name": "Кузнецова",
        "first_name": "Ольга",
        "patronymic": "Ивановна",
        "position": "старший преподаватель",
        "email": "kuznetsova@example.edu",
    },
    {
        "last_name": "Морозов",
        "first_name": "Дмитрий",
        "patronymic": "Сергеевич",
        "position": "профессор",
        "email": "morozov@example.edu",
    },
]

# (название, преподаватель, описание, семестры)
# Семестр: (учебный год, номер, лекции, практика, лабораторные)
ELECTIVES = [
    (
        "Python для начинающих",
        "Смирнов",
        "Базовый курс программирования на Python: синтаксис, структуры "
        "данных, функции, модули и небольшие учебные проекты.",
        [
            (ACADEMIC_YEAR_OLD, 1, 32, 16, 16),
            (ACADEMIC_YEAR_OLD, 2, 32, 16, 16),
        ],
    ),
    (
        "Web-разработка",
        "Кузнецова",
        "Создание веб-приложений: HTML и CSS, основы JavaScript, "
        "серверная логика, работа с базами данных и Django.",
        [
            (ACADEMIC_YEAR_OLD, 1, 32, 16, 12),
            (ACADEMIC_YEAR_NEW, 1, 32, 16, 12),
        ],
    ),
    (
        "Основы анализа данных",
        "Морозов",
        "Сбор и очистка данных, разведочный анализ, визуализация, "
        "базовые статистические методы и проверка гипотез.",
        [
            (ACADEMIC_YEAR_NEW, 1, 24, 12, 12),
        ],
    ),
]

STUDENTS = [
    {
        "last_name": "Иванов",
        "first_name": "Иван",
        "patronymic": "Иванович",
        "group": "СТ-25",
        "address": "ул. Ленина, 10",
        "phone": "890707070707",
    },
    {
        "last_name": "Петров",
        "first_name": "Алексей",
        "patronymic": "Сергеевич",
        "group": "ИС-24",
        "address": "ул. Гагарина, 15",
        "phone": "+7 900 222-33-44",
    },
    {
        "last_name": "Сидорова",
        "first_name": "Анна",
        "patronymic": "Викторовна",
        "group": "ПИ-22",
        "address": "ул. Центральная, 7",
        "phone": "+7 900 333-44-55",
    },
]

# (студент, факультатив, статус записи)
ENROLLMENTS = [
    ("Иванов", "Python для начинающих", Enrollment.STATUS_COMPLETED),
    ("Иванов", "Web-разработка", Enrollment.STATUS_ACTIVE),
    ("Петров", "Python для начинающих", Enrollment.STATUS_COMPLETED),
    ("Петров", "Основы анализа данных", Enrollment.STATUS_ACTIVE),
    ("Сидорова", "Web-разработка", Enrollment.STATUS_COMPLETED),
    ("Сидорова", "Основы анализа данных", Enrollment.STATUS_COMPLETED),
]

# (студент, факультатив, семестр, оценка, дата экзамена)
GRADES = [
    ("Иванов", "Python для начинающих", (ACADEMIC_YEAR_OLD, 1), 4, date(2026, 1, 15)),
    ("Иванов", "Python для начинающих", (ACADEMIC_YEAR_OLD, 2), 5, date(2026, 6, 10)),
    ("Петров", "Python для начинающих", (ACADEMIC_YEAR_OLD, 1), 3, date(2026, 1, 16)),
    ("Петров", "Python для начинающих", (ACADEMIC_YEAR_OLD, 2), 3, date(2026, 6, 11)),
    ("Сидорова", "Web-разработка", (ACADEMIC_YEAR_OLD, 1), 5, date(2026, 1, 18)),
    ("Сидорова", "Основы анализа данных", (ACADEMIC_YEAR_NEW, 1), 4, date(2026, 11, 10)),
]


class Command(BaseCommand):
    help = "Создать демонстрационные данные системы «Факультативы»."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Удалить все записи на факультативы и оценки, создать заново.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options["reset"]

        teachers = self.create_teachers()
        electives = self.create_electives(teachers)

        if reset:
            Grade.objects.all().delete()
            Enrollment.objects.all().delete()
            self.stdout.write("Записи и оценки удалены (--reset).")

        self.create_semesters(electives)

        students = self.create_students()
        self.create_enrollments(students, electives)
        self.create_grades(students, electives)

        self.stdout.write(
            self.style.SUCCESS(
                "Демонстрационные данные готовы: "
                f"преподавателей — {Teacher.objects.count()}, "
                f"факультативов — {Elective.objects.count()}, "
                f"студентов — {Student.objects.count()}, "
                f"записей — {Enrollment.objects.count()}, "
                f"оценок — {Grade.objects.count()}."
            )
        )

    # ------------------------------------------------------------------
    # Преподаватели
    # ------------------------------------------------------------------

    def create_teachers(self):
        teachers = {}

        for data in TEACHERS:
            teacher, _ = Teacher.objects.get_or_create(
                last_name=data["last_name"],
                first_name=data["first_name"],
                patronymic=data["patronymic"],
                defaults={
                    "position": data["position"],
                    "email": data["email"],
                },
            )

            teachers[data["last_name"]] = teacher

        return teachers

    # ------------------------------------------------------------------
    # Факультативы
    # ------------------------------------------------------------------

    def create_electives(self, teachers):
        electives = {}

        for name, teacher_last_name, description, _ in ELECTIVES:
            elective, created = Elective.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "teacher": teachers.get(teacher_last_name),
                },
            )

            if not created and elective.teacher is None:
                elective.teacher = teachers.get(teacher_last_name)
                elective.save(update_fields=["teacher"])

            electives[name] = elective

        return electives

    # ------------------------------------------------------------------
    # Учебный план по семестрам
    # ------------------------------------------------------------------

    def create_semesters(self, electives):
        for name, _, _, semesters in ELECTIVES:
            elective = electives[name]
            wanted = {(year, number) for year, number, *_ in semesters}

            for semester in elective.semesters.all():
                key = (semester.academic_year, semester.semester_number)

                if key in wanted:
                    continue

                if semester.grades.exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"Семестр {semester} содержит оценки — оставлен."
                        )
                    )
                    continue

                semester.delete()

            for year, number, lectures, practice, laboratory in semesters:
                ElectiveSemester.objects.update_or_create(
                    elective=elective,
                    academic_year=year,
                    semester_number=number,
                    defaults={
                        "lecture_hours": lectures,
                        "practice_hours": practice,
                        "laboratory_hours": laboratory,
                    },
                )

    # ------------------------------------------------------------------
    # Студенты
    # ------------------------------------------------------------------

    def create_students(self):
        students = {}

        for data in STUDENTS:
            student, _ = Student.objects.get_or_create(
                last_name=data["last_name"],
                first_name=data["first_name"],
                patronymic=data["patronymic"],
                group=data["group"],
                defaults={
                    "address": data["address"],
                    "phone": data["phone"],
                },
            )

            students[data["last_name"]] = student

        return students

    # ------------------------------------------------------------------
    # Записи и оценки
    # ------------------------------------------------------------------

    def create_enrollments(self, students, electives):
        for student_last_name, elective_name, status in ENROLLMENTS:
            Enrollment.objects.update_or_create(
                student=students[student_last_name],
                elective=electives[elective_name],
                defaults={"status": status},
            )

    def create_grades(self, students, electives):
        for (
            student_last_name,
            elective_name,
            (year, number),
            value,
            exam_date,
        ) in GRADES:
            semester = ElectiveSemester.objects.get(
                elective=electives[elective_name],
                academic_year=year,
                semester_number=number,
            )

            Grade.objects.get_or_create(
                student=students[student_last_name],
                elective_semester=semester,
                grade=value,
                exam_date=exam_date,
            )
