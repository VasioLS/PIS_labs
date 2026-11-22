/*
 * Клиентские сценарии системы «Факультативы».
 *
 * Файл подключается в students/base.html ко всем страницам и выполняет
 * только те действия, для которых на странице есть подходящие элементы:
 *
 * 1) живой поиск по карточкам студентов;
 * 2) сворачивание и разворачивание длинного описания факультатива;
 * 3) подтверждение отмены записи на факультатив;
 * 4) вывод таблицы студентов в консоль браузера.
 */

/*
 * Дополнение строки пробелами справа: аналог ljust() из Python.
 * В JavaScript нет встроенной функции выравнивания строк.
 */
function rpad(value, length) {
    var text = String(value);

    while (text.length < length) {
        text = text + " ";
    }

    return text;
}

/* Вывести список студентов в консоль в виде таблицы. */
function printStudents(students) {
    if (!students.length) {
        return;
    }

    console.log(
        rpad("Студент", 30),
        rpad("Группа", 10),
        rpad("Телефон", 20)
    );

    students.forEach(function (student) {
        console.log(
            rpad(student.name, 30),
            rpad(student.group, 10),
            rpad(student.phone, 20)
        );
    });
}

/* Собрать данные студентов из карточек на странице. */
function collectStudents() {
    var cards = document.querySelectorAll(".student-card");

    return Array.prototype.map.call(cards, function (card) {
        return {
            name: card.dataset.name || "",
            group: card.dataset.group || "",
            phone: card.dataset.phone || ""
        };
    });
}

/* Живой поиск по карточкам студентов. */
function initStudentSearch() {
    var input = document.getElementById("studentSearch");
    var grid = document.getElementById("studentsGrid");

    if (!input || !grid) {
        return;
    }

    var cards = grid.querySelectorAll(".student-card");

    input.addEventListener("input", function () {
        var query = input.value.toLowerCase().trim();

        Array.prototype.forEach.call(cards, function (card) {
            var text = card.textContent.toLowerCase();

            card.style.display = text.indexOf(query) === -1 ? "none" : "";
        });
    });
}

/* Свернуть/развернуть длинное описание факультатива. */
function initFoldButtons() {
    var buttons = document.querySelectorAll(".fold-button");

    Array.prototype.forEach.call(buttons, function (button) {
        button.addEventListener("click", function () {
            var target = document.getElementById(
                button.getAttribute("data-fold-target")
            );

            if (!target) {
                return;
            }

            var folded = target.classList.toggle("folded");

            button.textContent = folded
                ? "Показать полностью"
                : "Свернуть";
        });
    });
}

/* Подтверждение опасных действий (отмена записи на факультатив). */
function initConfirmForms() {
    var forms = document.querySelectorAll("form[data-confirm]");

    Array.prototype.forEach.call(forms, function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.confirm(form.getAttribute("data-confirm"))) {
                event.preventDefault();
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", function () {
    console.log("JavaScript системы «Факультативы» подключён.");

    initStudentSearch();
    initFoldButtons();
    initConfirmForms();

    printStudents(collectStudents());
});
