# make-planning-notes-for-nate

My senior colleague Nate asks for planning notes every 2 weeks, and I have forgotten to get them to him many a time even after he's already asked me. This tool was created to address my defective memory. It harnesses OpenAI's models to generate and send GitHub activity summaries automatically.

## Usage

Generate activity summaries from GitHub commits:

```bash
# Basic usage - look back 2 weeks and forecast 2 weeks ahead (default)
uv run src/get_commit_summary.py -u <github_username>

# Custom time periods using flexible offsets (e.g., 1 week past, 2 weeks future)
uv run src/get_commit_summary.py -u <github_username> -tp 1w -tf 2w

# Send email summary
uv run src/get_commit_summary.py -u <github_username> -e user@mskcc.org

# Display summary in console
uv run src/get_commit_summary.py -u <github_username> -d

# Run for Shaun
uv run src/get_commit_summary.py -u porwals -e porwals@mskcc.org
```

## Requirements

- `PERSONAL_GH_TOKEN` and/or `ENTERPRISE_GH_TOKEN` should be set in your `.env` file.
- For enterprise GitHub access, set `ENTERPRISE_GH_URL` (and use the `--enterprise` flag as needed).
- `GMAIL_EMAIL` and `GMAIL_APP_PASSWORD` are required (if you want to send email summaries).
- OpenAI API key must be set as `OPENAI_API_KEY` if you wish to generate commit summaries using GPT‑4.

## Example .env File

```env
# GitHub API Credentials
PERSONAL_GH_TOKEN=your_public_github_token_here
# For Enterprise GitHub (if applicable)
ENTERPRISE_GH_URL=https://your.enterprise.github.api.url
ENTERPRISE_GH_TOKEN=your_enterprise_github_token_here

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Gmail Email Configuration (for email sending)
GMAIL_EMAIL=your_email@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password
```

## Time Flag Examples

You can specify any valid time duration string:
- For days, e.g., `5d`
- For weeks, e.g., `2w`
- For years, e.g., `1y`

For example, to look back 14 days and project 1 year forward, you would run:

```bash
uv run src/get_commit_summary.py -u shaunporwal -tp 14d -tf 1y -d
```