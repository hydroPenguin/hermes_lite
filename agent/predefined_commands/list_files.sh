#!/bin/sh
# Lists files in the agent's root directory
printf "Listing files in /:"
ls -la /
printf "\nListing files in /agent_files/predefined_commands (inside container):"
ls -la /agent_files/predefined_commands