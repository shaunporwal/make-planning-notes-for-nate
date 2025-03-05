#!/bin/bash

# Script to schedule the commit summary job as a cron job
# that runs every 2 weeks at 9am on Wednesday EST

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Define the command to run
USERNAME="porwals"
EMAIL="porwals@mskcc.org"
COMMAND="cd $SCRIPT_DIR && uv run src/get_commit_summary.py -u $USERNAME -e $EMAIL"

# Create a temporary file for the crontab
TEMP_CRONTAB=$(mktemp)

# Export the current crontab to the temporary file
crontab -l > "$TEMP_CRONTAB" 2>/dev/null || echo "# Creating new crontab" > "$TEMP_CRONTAB"

# Check if the job already exists in the crontab
if grep -q "get_commit_summary.py -u $USERNAME" "$TEMP_CRONTAB"; then
    echo "Job already exists in crontab. Removing old entry..."
    grep -v "get_commit_summary.py -u $USERNAME" "$TEMP_CRONTAB" > "${TEMP_CRONTAB}.new"
    mv "${TEMP_CRONTAB}.new" "$TEMP_CRONTAB"
fi

# Add the new job to run every 2 weeks at 9am on Wednesday EST
echo "0 9 * * 3 [ \$((\$(date +\\%s) / 604800 % 2)) -eq 0 ] && $COMMAND" >> "$TEMP_CRONTAB"

# Install the new crontab
crontab "$TEMP_CRONTAB"

# Clean up the temporary file
rm "$TEMP_CRONTAB"

echo "Job scheduled to run every 2 weeks at 9am on Wednesday EST"
echo "Command: $COMMAND"

# Calculate the next run date - remove leading zeros to avoid octal interpretation
current_week_number=$(date +%U | sed 's/^0//')
if [ $((current_week_number % 2)) -eq 0 ]; then
    # Current week is even - schedule for today or in 2 weeks
    today=$(date +%u | sed 's/^0//')  # Day of week (1-7, Monday=1)
    if [ "$today" -eq 3 ]; then  # Wednesday
        # Handle hour without leading zero to avoid octal interpretation
        current_hour=$(date +%H | sed 's/^0//')
        if [ "$current_hour" -lt 9 ]; then
            echo "Next run: Today at 9am EST"
        else
            # For compatibility with BSD date on macOS
            if [ "$(uname)" = "Darwin" ]; then
                echo "Next run: $(date -v+2w '+%A, %B %d') at 9am EST"
            else
                echo "Next run: $(date -d '+2 weeks' '+%A, %B %d') at 9am EST"
            fi
        fi
    else
        # Find the next Wednesday
        days_until_wed=$((3 - today))
        if [ "$days_until_wed" -le 0 ]; then
            days_until_wed=$((days_until_wed + 7))
        fi

        # For compatibility with BSD date on macOS
        if [ "$(uname)" = "Darwin" ]; then
            echo "Next run: $(date -v+${days_until_wed}d '+%A, %B %d') at 9am EST"
        else
            echo "Next run: $(date -d "+$days_until_wed days" '+%A, %B %d') at 9am EST"
        fi
    fi
else
    # Current week is odd - schedule for next week
    today=$(date +%u | sed 's/^0//')  # Day of week (1-7, Monday=1)
    days_until_wed=$((3 - today + 7))
    if [ "$days_until_wed" -gt 7 ]; then
        days_until_wed=$((days_until_wed - 7))
    fi

    # For compatibility with BSD date on macOS
    if [ "$(uname)" = "Darwin" ]; then
        echo "Next run: $(date -v+${days_until_wed}d '+%A, %B %d') at 9am EST"
    else
        echo "Next run: $(date -d "+$days_until_wed days" '+%A, %B %d') at 9am EST"
    fi
fi

# Run the command immediately for the first time
echo "Running the command now for the first time..."
eval "$COMMAND"
