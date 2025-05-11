# Hermes Lite

A platform for securely executing predefined Linux commands on remote hosts.

## Overview

Hermes Lite allows engineers to remotely execute predefined Linux commands on specific internal hosts. It handles authentication, command execution tracking, and provides a web interface to view results.

## Features

- Trigger execution of predefined commands on target hosts
- Authentication and authorization through JWT
- Command execution tracking and history
- Real-time status updates
- Simple web interface

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Git

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/hermes_lite.git
cd hermes_lite
```

2. Start the containers:

```bash
docker-compose up -d
```

This will launch all required services:
- Web API (Flask)
- Worker (Celery)
- Message broker (RabbitMQ)
- Target hosts

3. Access the web interface at http://localhost:5001

### Usage

#### Registration & Login

1. Open http://localhost:5001 in your browser
2. Click on "Register" to create a new account
3. The first registered user automatically becomes an admin
4. Login with your credentials

#### Running Commands

1. After logging in, you'll see the command execution form
2. Select a command from the dropdown (e.g., "list_files.sh")
3. Choose a target host (Alpha or Beta)
4. Add parameters if needed (space-separated)
5. Click "Execute"

#### Viewing Results

1. Command status will be displayed immediately 
2. Click "View Output" to see the command output
3. For full history, click "Dashboard" to view all your executions

## Troubleshooting

- If you encounter any issues, check the container logs:
  ```bash
  docker-compose logs web
  docker-compose logs worker
  ```

- To restart the services:
  ```bash
  docker-compose restart
  ```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 