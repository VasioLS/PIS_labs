"""Расчёт минимального объёма факультативных часов студента.

Задача варианта: «Определение факультативов для студентов». Каждый студент
обязан прослушать не меньше минимального объёма факультативных предметов.
Здесь считается, сколько часов студент уже закрыл, сколько часов у него
в процессе, сколько часов ему не хватает и какие факультативы можно
предложить, чтобы этот минимум набрать.
"""

from dataclasses import dataclass, field

from django.db.models import F, Sum

from .models import (
    Elective,
    ElectiveSemester,
    Enrollment,
    Grade,
    HOURS_FIELDS,
    PASSING_GRADE,
    minimum_required_hours,
)


def hours_expression():
    """SQL-выражение суммы часов семестра (лекции + практика + лабораторные)."""

    expression = F(HOURS_FIELDS[0])

    for name in HOURS_FIELDS[1:]:
        expression = expression + F(name)

    return expression


def plan_totals():
    """Суммарные часы всего учебного плана по видам занятий."""

    totals = ElectiveSemester.objects.aggregate(
        **{name: Sum(name) for name in HOURS_FIELDS}
    )

    plan = {
        "lectures": totals["lecture_hours"] or 0,
        "practice": totals["practice_hours"] or 0,
        "laboratory": totals["laboratory_hours"] or 0,
    }

    plan["total"] = sum(plan.values())

    # Ширина полосок на главной странице — относительно самого
    # объёмного вида занятий.
    largest = max(plan["lectures"], plan["practice"], plan["laboratory"], 1)

    plan["lecture_width"] = round(plan["lectures"] * 100 / largest)
    plan["practice_width"] = round(plan["practice"] * 100 / largest)
    plan["laboratory_width"] = round(plan["laboratory"] * 100 / largest)

    return plan


@dataclass
class StudentProgress:
    """Успехи студента по факультативам."""

    student: object
    required_hours: int = 0
    credited_hours: int = 0
    planned_hours: int = 0
    passed_electives: int = 0
    enrolled_electives: int = 0
    electives: dict = field(default_factory=dict)

    @property
    def is_met(self):
        """Набрал ли студент минимальный объём часов."""

        return self.credited_hours >= self.required_hours

    @property
    def shortfall_hours(self):
        """Сколько часов не хватает до минимума."""

        return max(0, self.required_hours - self.credited_hours)

    @property
    def percent(self):
        """Процент выполнения минимума (0–100)."""

        if not self.required_hours:
            return 100

        return min(100, round(self.credited_hours * 100 / self.required_hours))

    @property
    def status_label(self):
        return "Минимум выполнен" if self.is_met else "Объём не набран"

    @property
    def status_css(self):
        return "success" if self.is_met else "warning"


def build_progress(students):
    """Посчитать прогресс для набора студентов за постоянное число запросов.

    Возвращает словарь ``{student_id: StudentProgress}``.
    """

    students = list(students)
    required = minimum_required_hours()

    progress = {
        student.pk: StudentProgress(student=student, required_hours=required)
        for student in students
    }

    if not progress:
        return progress

    student_ids = list(progress)

    semester_total = {}
    semester_elective = {}
    elective_total = {}

    for semester_id, elective_id, total in ElectiveSemester.objects.annotate(
        total=hours_expression()
    ).values_list("id", "elective_id", "total"):
        total = total or 0
        semester_total[semester_id] = total
        semester_elective[semester_id] = elective_id
        elective_total[elective_id] = elective_total.get(elective_id, 0) + total

    enrollments = (
        Enrollment.objects.filter(student_id__in=student_ids)
        .exclude(status=Enrollment.STATUS_CANCELLED)
        .values_list("student_id", "elective_id", "status")
    )

    enrolled = {student_id: set() for student_id in student_ids}
    active = {student_id: set() for student_id in student_ids}

    for student_id, elective_id, status in enrollments:
        enrolled[student_id].add(elective_id)
        progress[student_id].electives.setdefault(
            elective_id, elective_total.get(elective_id, 0)
        )

        if status == Enrollment.STATUS_ACTIVE:
            active[student_id].add(elective_id)

    for student_id, elective_ids in enrolled.items():
        progress[student_id].enrolled_electives = len(elective_ids)

    passed = (
        Grade.objects.filter(
            student_id__in=student_ids, grade__gte=PASSING_GRADE
        )
        .values_list("student_id", "elective_semester_id")
        .distinct()
    )

    # Оценки по отменённым записям остаются в журнале, но часы не зачитываются.
    cancelled = {
        (student_id, elective_id)
        for student_id, elective_id in Enrollment.objects.filter(
            student_id__in=student_ids,
            status=Enrollment.STATUS_CANCELLED,
        ).values_list("student_id", "elective_id")
    }

    passed_electives = {student_id: set() for student_id in student_ids}
    credited_by_elective = {student_id: {} for student_id in student_ids}

    for student_id, semester_id in passed:
        elective_id = semester_elective.get(semester_id)

        if elective_id is not None and (student_id, elective_id) in cancelled:
            continue

        item = progress[student_id]
        hours = semester_total.get(semester_id, 0)

        item.credited_hours += hours

        if elective_id is not None:
            passed_electives[student_id].add(elective_id)

            item.electives.setdefault(
                elective_id, elective_total.get(elective_id, 0)
            )

            credited_by_elective[student_id][elective_id] = (
                credited_by_elective[student_id].get(elective_id, 0) + hours
            )

    for student_id, elective_ids in passed_electives.items():
        progress[student_id].passed_electives = len(elective_ids)

    # «В процессе» — часы активных записей, которые ещё не закрыты
    # сданными семестрами. Завершённые факультативы уже в зачёте.
    for student_id, elective_ids in active.items():
        for elective_id in elective_ids:
            already = credited_by_elective[student_id].get(elective_id, 0)

            progress[student_id].planned_hours += max(
                0, elective_total.get(elective_id, 0) - already
            )

    return progress


def recommend_electives(progress, limit=None):
    """Подобрать факультативы, которые помогут набрать минимальный объём.

    Уже записанные (и уже пройденные) факультативы не предлагаются.
    Сначала идут варианты, которые полностью закрывают недостающий объём
    (из них — самый компактный), затем остальные — от большего к меньшему.
    """

    enrolled_ids = list(progress.electives)

    candidates = (
        Elective.objects.active()
        .exclude(pk__in=enrolled_ids)
        .prefetch_related("semesters")
    )

    rows = []

    for elective in candidates:
        hours = elective.total_hours
        after = progress.credited_hours + hours

        rows.append(
            {
                "elective": elective,
                "hours": hours,
                "after": after,
                "shortfall_after": max(0, progress.required_hours - after),
                "covers": after >= progress.required_hours,
            }
        )

    rows.sort(
        key=lambda row: (
            not row["covers"],
            row["hours"] if row["covers"] else -row["hours"],
        )
    )

    if limit is not None:
        rows = rows[:limit]

    return rows
