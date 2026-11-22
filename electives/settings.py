"""
Настройки Django-проекта «electives».

Проект реализует учёт факультативов студентов: анкетные данные,
учебный план по семестрам, записи на факультативы и оценки.
"""

from pathlib import Path

# Каталог проекта: electives/electives/../..
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: не используйте этот ключ в промышленной эксплуатации!
SECRET_KEY = "django-insecure-3vr2=zyc(3k8q$wv#dx397bg(t747o4=cwv9#3w$1io-n+s(v*"

# SECURITY WARNING: при развёртывании установите DEBUG = False.
DEBUG = True

# Локальная разработка: доступ разрешён только с этой машины.
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "[::1]",
    "testserver",
]


# Приложения проекта
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "students",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "electives.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "electives.wsgi.application"


# База данных: SQLite, файл рядом с manage.py.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Проверка паролей пользователей
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "NumericPasswordValidator",
    },
]


# Локализация и время
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True


# Статические файлы (CSS, JavaScript)
STATIC_URL = "/static/"


# Первичные ключи моделей
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Перенаправления при входе и выходе
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"


# Минимальный объём факультативных часов, который обязан прослушать
# каждый студент (вариант «Определение факультативов для студентов»).
# Используется в students.progress и на странице /requirements/.
MIN_ELECTIVE_HOURS = 128


# Почта: в учебном проекте письма выводятся в консоль.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}
