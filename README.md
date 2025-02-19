# make-planning-notes-for-nate

Nate asks for planning notes every 2 weeks usually, and this is an attempt to address my forgetfulness in getting them to him in a timely manner.

## Usage

Generate activity summaries from GitHub commits:

```bash
# Basic usage - look back 2 weeks and forward 2 weeks
uv run src/get_python_commits.py -u <github_username>

# Custom time periods
uv run src/get_python_commits.py -u <github_username> -wp 1 -wf 2  # 1 week past, 2 weeks future

# Send email summary
uv run src/get_python_commits.py -u <github_username> -e user@mskcc.org

# Display summary in console
uv run src/get_python_commits.py -u <github_username> -d
```

Requires:
- `GITHUB_ACCESS_TOKEN` in .env file
- `MSK_EMAIL` in .env file (for email functionality)
- Ollama running locally with llama3.1:70b model or openai api key in .env file.