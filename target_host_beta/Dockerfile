# target_host_beta/Dockerfile
FROM python:3.9-alpine AS base

WORKDIR /app

COPY /agent_files/requirements.txt /app/agent_requirements.txt
RUN pip install --no-cache-dir -r /app/agent_requirements.txt

COPY /agent_files/agent.py /app/agent.py
COPY /agent_files/predefined_commands /app/predefined_commands/

ENV AGENT_PORT=9000
ENV FLASK_APP=agent.py
ENV PYTHONUNBUFFERED=1

EXPOSE 9000

WORKDIR /agent_files
CMD ["python", "agent.py"]
