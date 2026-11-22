groupmates = [
    {
        "name": "Иван",
        "surname": "Петров",
        "exams": ["Python для начинающих", "Web-разработка", "Основы анализа данных"],
        "marks": [5, 4, 5]
    },
    {
        "name": "Анна",
        "surname": "Сидорова",
        "exams": ["Python для начинающих", "Web-разработка", "Основы анализа данных"],
        "marks": [4, 4, 3]
    },
    {
        "name": "Алексей",
        "surname": "Иванов",
        "exams": ["Python для начинающих", "Web-разработка", "Основы анализа данных"],
        "marks": [3, 3, 4]
    },
    {
        "name": "Мария",
        "surname": "Кузнецова",
        "exams": ["Python для начинающих", "Web-разработка", "Основы анализа данных"],
        "marks": [5, 5, 5]
    },
    {
        "name": "Дмитрий",
        "surname": "Смирнов",
        "exams": ["Python для начинающих", "Web-разработка", "Основы анализа данных"],
        "marks": [4, 5, 4]
    },
    {
        "name": "Ольга",
        "surname": "Попова",
        "exams": ["Python для начинающих", "Web-разработка", "Основы анализа данных"],
        "marks": [3, 4, 3]
    }
]
 
 
def average(student):
    return sum(student["marks"]) / len(student["marks"])
 
 
def print_students(students):
    print(u"Имя".ljust(10), u"Фамилия".ljust(12), u"Оценки".ljust(12), u"Средний балл".ljust(12))
    for student in students:
        print(student["name"].ljust(10),
              student["surname"].ljust(12),
              str(student["marks"]).ljust(12),
              str(round(average(student), 2)).ljust(12))
 
 
def filter_by_average(students, min_average):
    result = []
    for student in students:
        if average(student) > min_average:
            result.append(student)
    return result
 
 
print(u"Все студенты группы:")
print_students(groupmates)
 
value = input(u"Введите средний балл для фильтрации: ")
min_average = float(value.replace(",", "."))
 
filtered = filter_by_average(groupmates, min_average)
 
print()
print(u"Студенты со средним баллом выше", min_average, ":")
if filtered:
    print_students(filtered)
else:
    print(u"Таких студентов нет")
