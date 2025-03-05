# make-planning-notes-for-nate

Nate asks for planning notes every 2 weeks usually, and this is an attempt to address my forgetfulness in getting them to him in a timely manner.

## Usage

Generate activity summaries from GitHub commits:

```bash
# Basic usage - look back 2 weeks and forward 2 weeks
uv run src/get_commit_summary.py -u <github_username>

# Custom time periods
uv run src/get_commit_summary.py -u <github_username> -wp 1 -wf 2  # 1 week past, 2 weeks future

# Send email summary
uv run src/get_commit_summary.py -u <github_username> -e user@mskcc.org

# Display summary in console
uv run src/get_commit_summary.py -u <github_username> -d
```

Requires:
- `GITHUB_ACCESS_TOKEN` in .env file
- `MSK_EMAIL` in .env file (for email functionality)
- Ollama running locally with llama3.1:70b model or openai api key in .env file.

## Scheduled Job

A scheduling script is provided to set up a cron job that runs the commit summary every 2 weeks at 9am on Wednesday EST.

### Setup

To set up the scheduled job:

```bash
# Make the script executable (if not already)
chmod +x schedule_commit_summary.sh

# Run the setup script
./schedule_commit_summary.sh
```

The script will:
1. Schedule the job to run every 2 weeks at 9am on Wednesday EST
2. Run the command immediately for the first time
3. Display when the next scheduled run will occur

### Managing the Job

To view the current cron jobs:
```bash
crontab -l
```

To remove the scheduled job:
```bash
# Using the provided script
./remove_scheduled_job.sh

# Or manually
crontab -l | grep -v "get_commit_summary.py" | crontab -
```

To reschedule or modify the job, simply run the setup script again:
```bash
./schedule_commit_summary.sh
```
