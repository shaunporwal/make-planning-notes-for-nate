#!/bin/bash

# Script to remove the scheduled commit summary job

echo "Removing scheduled commit summary job..."

# Create a temporary file for the crontab
TEMP_CRONTAB=$(mktemp)

# Export the current crontab to the temporary file
crontab -l > "$TEMP_CRONTAB" 2>/dev/null || echo "No existing crontab found."

# Check if the job exists in the crontab
if grep -q "get_commit_summary.py" "$TEMP_CRONTAB"; then
    echo "Job found in crontab. Removing..."
    grep -v "get_commit_summary.py" "$TEMP_CRONTAB" > "${TEMP_CRONTAB}.new"
    mv "${TEMP_CRONTAB}.new" "$TEMP_CRONTAB"
    crontab "$TEMP_CRONTAB"
    echo "Job removed successfully."
else
    echo "No commit summary job found in crontab."
fi

# Clean up the temporary file
rm "$TEMP_CRONTAB"
