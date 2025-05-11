#!/bin/sh
# Simulates a long-running task by printing messages for 3 minutes

# Ensure output is not buffered using shell techniques
# Force line buffering by redirecting to /dev/tty or stdout
exec 1>&1           # Redirect stdout to the original stdout
echo "Starting long-running task..."
echo "This task will run for approximately 3 minutes..."
# Explicitly flush after each echo by using /dev/tty
echo "Output should be unbuffered" > /dev/tty

# Calculate end time (current time + 180 seconds)
END_TIME=$(( $(date +%s) + 180 ))

# Initialize counter
COUNTER=1

# Run until we reach the end time
while [ $(date +%s) -lt $END_TIME ]
do
    # Print progress message
    echo "Task progress: step $COUNTER at $(date +"%H:%M:%S")"
    
    # Explicitly flush output (works in most shells)
    sync
    
    # Sleep for 5 seconds
    sleep 5
    
    # Increment counter
    COUNTER=$((COUNTER+1))
done

echo "Task completed successfully after $COUNTER steps!"
echo "Long-running task finished at $(date +"%H:%M:%S")" 