FROM python:3.9-slim-buster AS base

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables (you might adjust these based on your app)
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
ENV CELERY_BROKER_URL=amqp://user:password@rabbitmq:5672//
ENV CELERY_RESULT_BACKEND=db+sqlite:///data/hermes_lite.db
ENV DATABASE_URL=sqlite:///data/hermes_lite.db

# Expose the Flask application port
EXPOSE 5000

# Create the data directory and set ownership
RUN mkdir -p /app/data
RUN chown -R $(id -u):$(id -g) /app/data

# Command to run the Flask development server (for the 'web' service)
# The 'worker' service will override this command in docker-compose.yml
CMD ["flask", "run", "--host=0.0.0.0"]