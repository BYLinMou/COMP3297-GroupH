FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Project currently has no requirements.txt; install Django directly.
RUN pip install --no-cache-dir "Django==5.2.12"

COPY . /app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
