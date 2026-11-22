"""Привести учебные годы семестров к формату «2026/2027».

В базе встречались значения вида «Учебный год: 2026/20», «2028» и «2027»,
из-за которых учебный план отображался неаккуратно. Миграция разбирает
номер года из строки и записывает единый формат.
"""

import re

from django.db import migrations

YEAR_PATTERN = r"(\d{4})\D+(\d{2,4})"

DEFAULT_ACADEMIC_YEAR = "2026/2027"


def normalize_academic_year(value, default=DEFAULT_ACADEMIC_YEAR):
    """Вернуть учебный год в формате «ГГГГ/ГГГГ»."""

    text = (value or "").strip()

    match = re.search(YEAR_PATTERN, text)

    if match is None:
        return default

    start = match.group(1)
    end = match.group(2)

    if len(end) == 2:
        end = start[:2] + end

    if int(end) != int(start) + 1:
        end = str(int(start) + 1)

    return f"{start}/{end}"


def clean_academic_years(apps, schema_editor):
    ElectiveSemester = apps.get_model("students", "ElectiveSemester")

    for semester in ElectiveSemester.objects.all():
        year = normalize_academic_year(semester.academic_year)

        if year != semester.academic_year:
            semester.academic_year = year
            semester.save(update_fields=["academic_year"])


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0002_schema_v2"),
    ]

    operations = [
        migrations.RunPython(clean_academic_years, migrations.RunPython.noop),
    ]
