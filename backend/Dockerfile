FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application
COPY main.py .
COPY .env .

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
