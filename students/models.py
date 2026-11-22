"""Модели предметной области приложения «Факультативы».

Вариант: «Определение факультативов для студентов».

Предметная область:

* преподаватели кафедры обеспечивают проведение факультативных занятий
  по предметам (модель :class:`Teacher`);
* хранятся анкетные данные студентов: ФИО, группа, адрес, телефон
  (модель :class:`Student`);
* у каждого факультатива есть план занятий: объём лекций, практик и
  лабораторных работ задаётся отдельно для каждого семестра, поэтому
  факультатив может длиться несколько семестров
  (модели :class:`Elective` и :class:`ElectiveSemester`);
* студент записывается на факультатив (:class:`Enrollment`), а по
  окончании семестра получает оценку за экзамен (:class:`Grade`);
* итоговой оценкой за предмет считается последняя полученная оценка —
  см. :func:`final_grade` и :func:`final_grades_map`.
"""

from functools import cached_property

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

#: Минимальная положительная оценка: с неё начинается «зачёт» по предмету.
PASSING_GRADE = 3

#: Допустимые оценки на экзамене.
GRADE_CHOICES = [
    (2, "2 — неудовлетворительно"),
    (3, "3 — удовлетворительно"),
    (4, "4 — хорошо"),
    (5, "5 — отлично"),
]

#: Номера семестров, в которых может идти факультатив.
SEMESTER_CHOICES = [
    (1, "1 семестр"),
    (2, "2 семестр"),
]

#: Поля с часами занятий: сумма этих полей даёт объём семестра.
HOURS_FIELDS = ("lecture_hours", "practice_hours", "laboratory_hours")


class PersonMixin:
    """Общие свойства для людей: студенты и преподаватели."""

    @property
    def full_name(self):
        """Фамилия, имя и отчество одной строкой."""

        parts = [self.last_name, self.first_name, self.patronymic]

        return " ".join(part for part in parts if part)

    @property
    def short_name(self):
        """Фамилия и инициалы: «Иванов И. И.»."""

        initials = "".join(
            f"{part[0]}." for part in (self.first_name, self.patronymic) if part
        )

        return f"{self.last_name} {initials}".strip()


class Teacher(PersonMixin, models.Model):
    """Преподаватель кафедры, ведущий факультативные занятия."""

    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    patronymic = models.CharField(
        max_length=100, blank=True, verbose_name="Отчество"
    )
    position = models.CharField(
        max_length=100, blank=True, verbose_name="Должность"
    )
    department = models.CharField(
        max_length=150, default="Кафедра информатики", verbose_name="Кафедра"
    )
    email = models.EmailField(blank=True, verbose_name="Электронная почта")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Телефон")

    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "Преподаватели"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name


class Student(PersonMixin, models.Model):
    """Студент и его анкетные данные."""

    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    patronymic = models.CharField(
        max_length=100, blank=True, verbose_name="Отчество"
    )
    group = models.CharField(max_length=50, verbose_name="Группа")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    phone = models.CharField(max_length=30, verbose_name="Телефон")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Добавлен")

    class Meta:
        verbose_name = "Студент"
        verbose_name_plural = "Студенты"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name


class ElectiveQuerySet(models.QuerySet):
    """Дополнительные выборки по факультативам."""

    def active(self):
        return self.filter(is_active=True)


class Elective(models.Model):
    """Факультативный предмет, который ведёт преподаватель кафедры."""

    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="electives",
        verbose_name="Преподаватель",
    )
    is_active = models.BooleanField(default=True, verbose_name="Набор открыт")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    objects = ElectiveQuerySet.as_manager()

    class Meta:
        verbose_name = "Факультатив"
        verbose_name_plural = "Факультативы"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @cached_property
    def semesters_list(self):
        """Семестры факультатива в порядке учебного плана.

        Сортировка выполняется в Python, чтобы использовать данные
        ``prefetch_related`` и не порождать отдельный запрос.
        """

        return sorted(
            self.semesters.all(),
            key=lambda semester: (
                semester.academic_year,
                semester.semester_number,
            ),
        )

    @property
    def duration_semesters(self):
        """Сколько семестров длится факультатив."""

        return len(self.semesters_list)

    @cached_property
    def total_hours(self):
        """Общий объём факультатива по всем семестрам, часов."""

        return sum(semester.total_hours for semester in self.semesters_list)

    @cached_property
    def hours_by_type(self):
        """Объём факультатива по видам занятий."""

        return {
            "lectures": sum(s.lecture_hours for s in self.semesters_list),
            "practice": sum(s.practice_hours for s in self.semesters_list),
            "laboratory": sum(s.laboratory_hours for s in self.semesters_list),
        }

    @property
    def students_count(self):
        """Число студентов, записанных на факультатив."""

        return self.enrollments.exclude(
            status=Enrollment.STATUS_CANCELLED
        ).count()

    @property
    def is_multisemester(self):
        """Длится ли факультатив больше одного семестра."""

        return self.duration_semesters > 1


class ElectiveSemester(models.Model):
    """Объём занятий факультатива в конкретном семестре."""

    elective = models.ForeignKey(
        Elective,
        on_delete=models.CASCADE,
        related_name="semesters",
        verbose_name="Факультатив",
    )
    academic_year = models.CharField(
        max_length=20,
        help_text="Например: 2026/2027",
        verbose_name="Учебный год",
    )
    semester_number = models.PositiveSmallIntegerField(
        choices=SEMESTER_CHOICES, verbose_name="Семестр"
    )
    lecture_hours = models.PositiveIntegerField(
        default=0, verbose_name="Лекции, часов"
    )
    practice_hours = models.PositiveIntegerField(
        default=0, verbose_name="Практика, часов"
    )
    laboratory_hours = models.PositiveIntegerField(
        default=0, verbose_name="Лабораторные, часов"
    )

    class Meta:
        verbose_name = "Семестр факультатива"
        verbose_name_plural = "Семестры факультативов"
        ordering = ["academic_year", "semester_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["elective", "academic_year", "semester_number"],
                name="unique_elective_semester",
            )
        ]

    def __str__(self):
        return (
            f"{self.elective.name} — "
            f"{self.academic_year}, "
            f"{self.semester_number} семестр"
        )

    @property
    def total_hours(self):
        """Суммарный объём семестра по всем видам занятий, часов."""

        return sum(getattr(self, field) for field in HOURS_FIELDS)


class Enrollment(models.Model):
    """Запись студента на факультатив."""

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Обучается"),
        (STATUS_COMPLETED, "Завершил"),
        (STATUS_CANCELLED, "Отменена"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Студент",
    )
    elective = models.ForeignKey(
        Elective,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Факультатив",
    )
    enrolled_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Дата записи"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name="Статус",
    )

    class Meta:
        verbose_name = "Запись на факультатив"
        verbose_name_plural = "Записи на факультативы"
        ordering = ["-enrolled_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "elective"],
                name="unique_student_elective",
            )
        ]

    def __str__(self):
        return f"{self.student} — {self.elective}"

    @property
    def is_cancelled(self):
        return self.status == self.STATUS_CANCELLED

    @property
    def status_label(self):
        return self.get_status_display()


class Grade(models.Model):
    """Оценка, полученная студентом на экзамене по факультативу."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="grades",
        verbose_name="Студент",
    )
    elective_semester = models.ForeignKey(
        ElectiveSemester,
        on_delete=models.CASCADE,
        related_name="grades",
        verbose_name="Семестр факультатива",
    )
    grade = models.PositiveSmallIntegerField(
        choices=GRADE_CHOICES,
        validators=[
            MinValueValidator(min(value for value, _ in GRADE_CHOICES)),
            MaxValueValidator(max(value for value, _ in GRADE_CHOICES)),
        ],
        verbose_name="Оценка",
    )
    exam_date = models.DateField(verbose_name="Дата экзамена")

    class Meta:
        verbose_name = "Оценка"
        verbose_name_plural = "Оценки"
        ordering = ["-exam_date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(grade__gte=2, grade__lte=5),
                name="grade_between_2_and_5",
            )
        ]

    def __str__(self):
        return f"{self.student} — {self.elective.name}: {self.grade}"

    @property
    def elective(self):
        """Факультатив, к которому относится оценка."""

        return self.elective_semester.elective

    @property
    def is_passing(self):
        """Зачтена ли оценка (3 и выше)."""

        return self.grade >= PASSING_GRADE

    @property
    def exam_date_label(self):
        return self.exam_date.strftime("%d.%m.%Y")


def final_grade(student, elective):
    """Итоговая оценка студента за факультатив.

    По условию задачи итоговой считается *последняя* полученная оценка,
    поэтому сортировка идёт по дате экзамена, а при равных датах —
    по порядку внесения записи.
    """

    return (
        Grade.objects.filter(
            student=student, elective_semester__elective=elective
        )
        .select_related("elective_semester__elective")
        .order_by("exam_date", "id")
        .last()
    )


def final_grades_map(student_ids=None, elective_id=None):
    """Итоговые оценки студентов.

    Возвращает словарь ``{(student_id, elective_id): Grade}``, в котором
    для каждой пары остаётся последняя (по дате экзамена) оценка. Выборку
    можно ограничить студентами и/или факультативом.
    """

    result = {}

    grades = Grade.objects.select_related("elective_semester").order_by(
        "exam_date", "id"
    )

    if student_ids is not None:
        grades = grades.filter(student_id__in=student_ids)

    if elective_id is not None:
        grades = grades.filter(elective_semester__elective_id=elective_id)

    for grade in grades:
        key = (grade.student_id, grade.elective_semester.elective_id)
        result[key] = grade

    return result


def minimum_required_hours():
    """Минимальный объём факультативных часов на одного студента."""

    return int(getattr(settings, "MIN_ELECTIVE_HOURS", 160))
