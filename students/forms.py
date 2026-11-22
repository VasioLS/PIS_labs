"""Формы приложения: анкета студента и выставление оценки."""

import re

from django import forms
from django.utils import timezone

from .models import (
    ElectiveSemester,
    Enrollment,
    Grade,
    PASSING_GRADE,
    Student,
)

PHONE_RE = re.compile(r"^\+?[\d\s()\-]{10,25}$")


def phone_digits(value):
    """Количество цифр в номере телефона."""

    return len(re.sub(r"\D", "", value))


class StudentForm(forms.ModelForm):
    """Анкета студента с проверкой обязательных полей и телефона."""

    class Meta:
        model = Student
        fields = [
            "last_name",
            "first_name",
            "patronymic",
            "group",
            "address",
            "phone",
        ]
        widgets = {
            "last_name": forms.TextInput(attrs={"placeholder": "Иванов"}),
            "first_name": forms.TextInput(attrs={"placeholder": "Иван"}),
            "patronymic": forms.TextInput(attrs={"placeholder": "Иванович"}),
            "group": forms.TextInput(attrs={"placeholder": "СТ-25"}),
            "address": forms.TextInput(
                attrs={"placeholder": "г. Москва, ул. Ленина, 10"}
            ),
            "phone": forms.TextInput(
                attrs={"placeholder": "+7 900 000-00-00"}
            ),
        }

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip().title()

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip().title()

    def clean_patronymic(self):
        return self.cleaned_data["patronymic"].strip().title()

    def clean_group(self):
        return self.cleaned_data["group"].strip().upper()

    def clean_address(self):
        return self.cleaned_data["address"].strip()

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()

        if not PHONE_RE.match(phone) or phone_digits(phone) < 10:
            raise forms.ValidationError(
                "Телефон должен содержать не менее 10 цифр; "
                "допускаются знаки «+», «-», пробелы и скобки."
            )

        return phone


class GradeForm(forms.ModelForm):
    """Выставление оценки за экзамен по семестру факультатива."""

    class Meta:
        model = Grade
        fields = ["student", "elective_semester", "grade", "exam_date"]
        widgets = {
            "exam_date": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fixed_student = student

        semesters = (
            ElectiveSemester.objects.select_related("elective")
            .order_by("elective__name", "academic_year", "semester_number")
        )

        if student is not None:
            self.fields.pop("student")

            semesters = semesters.filter(
                elective__enrollments__student=student,
                elective__enrollments__status__in=[
                    Enrollment.STATUS_ACTIVE,
                    Enrollment.STATUS_COMPLETED,
                ],
            ).distinct()

        self.fields["elective_semester"].queryset = semesters
        self.fields["exam_date"].initial = timezone.localdate()

        if not self.is_bound:
            self.fields["grade"].initial = PASSING_GRADE

    def clean(self):
        cleaned = super().clean()

        student = self.fixed_student or cleaned.get("student")
        semester = cleaned.get("elective_semester")

        if student and semester:
            enrolled = Enrollment.objects.filter(
                student=student,
                elective=semester.elective,
                status__in=[
                    Enrollment.STATUS_ACTIVE,
                    Enrollment.STATUS_COMPLETED,
                ],
            ).exists()

            if not enrolled:
                self.add_error(
                    "elective_semester",
                    "Студент не записан на этот факультатив: "
                    "сначала оформите запись.",
                )

        exam_date = cleaned.get("exam_date")

        if exam_date and exam_date > timezone.localdate():
            self.add_error(
                "exam_date", "Дата экзамена не может быть в будущем."
            )

        return cleaned

    def save(self, commit=True):
        grade = super().save(commit=False)

        if self.fixed_student is not None:
            grade.student = self.fixed_student

        if commit:
            grade.save()

        return grade
