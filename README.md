# Hermes Lite

A simple system for running predefined commands on remote hosts.

## What It Does

Hermes Lite lets you run specific shell scripts on remote hosts through a web interface. It:

- Provides a clean, minimal web interface
- Executes commands securely in containers
- Tracks command history and results
- Shows command output in real-time
- Makes command results accessible to everyone

## How It Works

The system has four parts:
1. **Web Interface** - Where users select and run commands
2. **Workers** - Execute commands asynchronously
3. **Message Queue** - Connects web interface to workers
4. **Target Hosts** - Where commands actually run

## Quick Start

### Requirements
- Docker and Docker Compose
- Git

### Setup

```bash
# Get the code and start the system
git clone https://github.com/hydroPenguin/hermes_lite
cd hermes_lite
docker-compose up -d

# Access the web interface
# http://localhost:5001
```

### Using Hermes Lite

1. **Register & Login**
   - First registered user becomes admin
   - Login with your credentials

2. **Run Commands**
   - Choose a command (e.g., list_files.sh)
   - Select a target host
   - Add parameters if needed
   - Click "Execute"

3. **View Results**
   - Status appears immediately
   - Click "View Output" to see results
   - All users can view command outputs
   - Use "Dashboard" to see execution history

## License

MIT License 