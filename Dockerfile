FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# The official Python image selects its native ARM64 variant on the Oracle host.
RUN pip install --no-cache-dir Flask==3.1.0 openai==1.99.5 python-dotenv==1.1.0 gunicorn==23.0.0 pypdf==4.2.0

# Copy only runtime files so a local .env never enters the image.
COPY app.py .
COPY assets/ ./assets/

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
