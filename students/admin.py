"""Настройка административной панели Django для приложения «Факультативы»."""

from django.contrib import admin

from .models import (
    Elective,
    ElectiveSemester,
    Enrollment,
    Grade,
    Student,
    Teacher,
)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    """Преподаватели кафедры."""

    list_display = (
        "last_name",
        "first_name",
        "patronymic",
        "position",
        "department",
        "email",
    )
    list_filter = ("department", "position")
    search_fields = ("last_name", "first_name", "patronymic", "email")


class ElectiveSemesterInline(admin.TabularInline):
    """Учебный план факультатива задаётся прямо в его карточке."""

    model = ElectiveSemester
    extra = 0
    fields = (
        "academic_year",
        "semester_number",
        "lecture_hours",
        "practice_hours",
        "laboratory_hours",
    )


@admin.register(Elective)
class ElectiveAdmin(admin.ModelAdmin):
    """Факультативы и их семестры."""

    list_display = (
        "name",
        "teacher",
        "duration_semesters",
        "total_hours",
        "students_count",
        "is_active",
    )
    list_filter = ("is_active", "teacher")
    search_fields = ("name", "description", "teacher__last_name")
    list_select_related = ("teacher",)
    inlines = (ElectiveSemesterInline,)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        return queryset.prefetch_related("semesters", "enrollments")


@admin.register(ElectiveSemester)
class ElectiveSemesterAdmin(admin.ModelAdmin):
    """Семестры факультативов: объём лекций, практик и лабораторных."""

    list_display = (
        "elective",
        "academic_year",
        "semester_number",
        "lecture_hours",
        "practice_hours",
        "laboratory_hours",
        "total_hours",
    )
    list_filter = ("academic_year", "semester_number")
    search_fields = ("elective__name",)
    list_select_related = ("elective",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Студенты и их анкетные данные."""

    list_display = (
        "last_name",
        "first_name",
        "patronymic",
        "group",
        "phone",
        "address",
    )
    list_filter = ("group",)
    search_fields = ("last_name", "first_name", "patronymic", "group", "phone")
    list_per_page = 25


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Записи студентов на факультативы."""

    list_display = (
        "student",
        "elective",
        "status",
        "enrolled_at",
    )
    list_filter = ("status", "elective")
    search_fields = (
        "student__last_name",
        "student__first_name",
        "elective__name",
    )
    list_select_related = ("student", "elective")


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    """Оценки, полученные студентами на экзаменах."""

    list_display = (
        "student",
        "elective",
        "semester",
        "grade",
        "exam_date",
    )
    list_filter = ("grade", "exam_date", "elective_semester__elective")
    search_fields = (
        "student__last_name",
        "student__first_name",
        "elective_semester__elective__name",
    )
    list_select_related = ("student", "elective_semester__elective")
    date_hierarchy = "exam_date"

    @admin.display(description="Факультатив")
    def elective(self, obj):
        return obj.elective_semester.elective.name

    @admin.display(description="Семестр")
    def semester(self, obj):
        semester = obj.elective_semester

        return f"{semester.academic_year}, {semester.semester_number} сем."
