"""Схема приложения «Факультативы» после доработки.

Что меняется:

* появляется модель преподавателя кафедры;
* у факультатива больше нет собственного «минимального объёма часов» —
  объём считается по семестрам, а минимум для студента задаётся настройкой
  ``MIN_ELECTIVE_HOURS``;
* запись студента привязывается к факультативу (а не к отдельному
  семестру), чтобы многoсеместровый факультатив был одним предметом;
* добавляются ограничения целостности: одна запись на пару
  «студент + факультатив», один семестр на учебный год и оценка от 2 до 5.
"""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def copy_elective_from_semester(apps, schema_editor):
    """Перенести факультатив из записи-семестра в саму запись."""

    Enrollment = apps.get_model("students", "Enrollment")

    for enrollment in Enrollment.objects.select_related(
        "elective_semester"
    ).all():
        enrollment.elective_id = enrollment.elective_semester.elective_id
        enrollment.save(update_fields=["elective"])


def restore_semester_from_elective(apps, schema_editor):
    """Обратный перенос: выбрать первый семестр факультатива."""

    Enrollment = apps.get_model("students", "Enrollment")

    for enrollment in Enrollment.objects.all():
        semester = enrollment.elective.semesters.order_by(
            "academic_year", "semester_number"
        ).first()

        if semester is not None:
            enrollment.elective_semester_id = semester.pk
            enrollment.save(update_fields=["elective_semester"])


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0001_initial"),
    ]

    operations = [
        # --- Преподаватели -------------------------------------------------
        migrations.CreateModel(
            name="Teacher",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "last_name",
                    models.CharField(max_length=100, verbose_name="Фамилия"),
                ),
                (
                    "first_name",
                    models.CharField(max_length=100, verbose_name="Имя"),
                ),
                (
                    "patronymic",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="Отчество"
                    ),
                ),
                (
                    "position",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="Должность"
                    ),
                ),
                (
                    "department",
                    models.CharField(
                        default="Кафедра информатики",
                        max_length=150,
                        verbose_name="Кафедра",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        verbose_name="Электронная почта",
                    ),
                ),
                (
                    "phone",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="Телефон"
                    ),
                ),
            ],
            options={
                "verbose_name": "Преподаватель",
                "verbose_name_plural": "Преподаватели",
                "ordering": ["last_name", "first_name"],
            },
        ),
        migrations.AddField(
            model_name="elective",
            name="teacher",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="electives",
                to="students.teacher",
                verbose_name="Преподаватель",
            ),
        ),
        migrations.RemoveField(
            model_name="elective",
            name="minimum_hours",
        ),
        migrations.AlterModelOptions(
            name="elective",
            options={
                "ordering": ["name"],
                "verbose_name": "Факультатив",
                "verbose_name_plural": "Факультативы",
            },
        ),
        migrations.AlterField(
            model_name="elective",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, verbose_name="Создан"
            ),
        ),
        migrations.AlterField(
            model_name="elective",
            name="is_active",
            field=models.BooleanField(
                default=True, verbose_name="Набор открыт"
            ),
        ),
        # --- Запись на факультатив ----------------------------------------
        migrations.AddField(
            model_name="enrollment",
            name="elective",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="enrollments",
                to="students.elective",
                verbose_name="Факультатив",
            ),
        ),
        migrations.RunPython(
            copy_elective_from_semester,
            restore_semester_from_elective,
        ),
        migrations.RemoveField(
            model_name="enrollment",
            name="elective_semester",
        ),
        migrations.AlterField(
            model_name="enrollment",
            name="elective",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="enrollments",
                to="students.elective",
                verbose_name="Факультатив",
            ),
        ),
        migrations.AlterModelOptions(
            name="enrollment",
            options={
                "ordering": ["-enrolled_at", "-id"],
                "verbose_name": "Запись на факультатив",
                "verbose_name_plural": "Записи на факультативы",
            },
        ),
        migrations.AddConstraint(
            model_name="enrollment",
            constraint=models.UniqueConstraint(
                fields=("student", "elective"),
                name="unique_student_elective",
            ),
        ),
        # --- Семестры факультативов ---------------------------------------
        migrations.AlterField(
            model_name="electivesemester",
            name="academic_year",
            field=models.CharField(
                help_text="Например: 2026/2027",
                max_length=20,
                verbose_name="Учебный год",
            ),
        ),
        migrations.AlterModelOptions(
            name="electivesemester",
            options={
                "ordering": ["academic_year", "semester_number", "id"],
                "verbose_name": "Семестр факультатива",
                "verbose_name_plural": "Семестры факультативов",
            },
        ),
        migrations.AddConstraint(
            model_name="electivesemester",
            constraint=models.UniqueConstraint(
                fields=("elective", "academic_year", "semester_number"),
                name="unique_elective_semester",
            ),
        ),
        # --- Оценки -------------------------------------------------------
        migrations.AlterField(
            model_name="grade",
            name="elective_semester",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="grades",
                to="students.electivesemester",
                verbose_name="Семестр факультатива",
            ),
        ),
        migrations.AlterField(
            model_name="grade",
            name="grade",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (2, "2 — неудовлетворительно"),
                    (3, "3 — удовлетворительно"),
                    (4, "4 — хорошо"),
                    (5, "5 — отлично"),
                ],
                validators=[
                    django.core.validators.MinValueValidator(2),
                    django.core.validators.MaxValueValidator(5),
                ],
                verbose_name="Оценка",
            ),
        ),
        migrations.AlterModelOptions(
            name="grade",
            options={
                "ordering": ["-exam_date", "-id"],
                "verbose_name": "Оценка",
                "verbose_name_plural": "Оценки",
            },
        ),
        migrations.AddConstraint(
            model_name="grade",
            constraint=models.CheckConstraint(
                condition=models.Q(("grade__gte", 2), ("grade__lte", 5)),
                name="grade_between_2_and_5",
            ),
        ),
        # --- Студенты -----------------------------------------------------
        migrations.AlterField(
            model_name="student",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, verbose_name="Добавлен"
            ),
        ),
    ]
