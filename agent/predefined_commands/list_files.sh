#!/bin/sh
# Lists files in the agent's root directory
echo "Listing files in /:"
ls -la /
echo "\nListing files in /agent_files/predefined_commands (inside container):"
ls -la /agent_files/predefined_commands