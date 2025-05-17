#!/bin/sh
# Simulates a long-running task by printing messages for 3 minutes

# Ensure output is not buffered using shell techniques
exec 1>&1           # Redirect stdout to the original stdout
echo "Starting long-running task..."
echo "This task will run for approximately 0.5 minutes..."

# Calculate end time (current time + 180 seconds)
END_TIME=$(( $(date +%s) + 30 ))

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