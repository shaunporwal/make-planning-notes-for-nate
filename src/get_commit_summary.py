from github import Github
import os
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
import pytz
import openai
import argparse
import smtplib
from email.mime.text import MIMEText
import socket
import re

# Load .env from the parent directory (adjust as needed)
dotenv_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path)


def parse_time_delta(duration_str: str) -> timedelta:
    """
    Convert a duration string into a timedelta.
    Supported units:
        s - seconds
        m - minutes
        h - hours
        d - days (or no unit)
        w - weeks
        y - years (assumed to be 365 days)
    For example: "2w" returns a timedelta of 2 weeks.
    """
    
    duration_str = duration_str.strip().lower()
    pattern = r"^(\d+(?:\.\d+)?)([smhdwy]?)$"
    match = re.match(pattern, duration_str)
    if not match:
        raise ValueError(f"Invalid time duration format: {duration_str}")
    value, unit = match.groups()
    value = float(value)
    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d" or unit == "":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    elif unit == "y":
        return timedelta(days=value * 365)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")


class CommitTracker:
    def __init__(self, username):
        # Load environment variables
        load_dotenv()
        token = os.getenv("PERSONAL_GH_TOKEN")
        self.username = username
        self.github = self._initialize_github(token)

    def _initialize_github(self, token):
        """Initialize GitHub connection with error handling"""
        g = Github(login_or_token=token)
        g.get_user(self.username)
        return g

    def get_activity(self):
        """Get all GitHub activity from the specified time offset until now"""


        repos = self.github.get_repos()

        all_activity = []


        return repos



    def _format_activity(self, commits):
        """Format commits by date for easy reporting"""
        commits.sort(key=lambda x: x["date"], reverse=True)
        formatted_output = []
        current_date = None

        for commit in commits:
            commit_date = commit["date"].strftime("%Y-%m-%d")
            if commit_date != current_date:
                current_date = commit_date
                formatted_output.append(f"\n=== {commit_date} ===")
            formatted_output.append(f"[{commit['repo']}] {commit['message']}")

        return formatted_output

    def generate_commit_summary(self, past_delta: timedelta, future_delta: timedelta):
        """Generate a bulleted summary of commits using OpenAI."""
        try:
            commits = self.get_activity(past_delta, verbose=False)
            if not commits:
                return "No commits found in the specified time period."
            commit_text = "\n".join(commits)
            end_date = datetime.now()
            start_date = end_date - past_delta
            next_period_end = end_date + future_delta
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            instruction = (
                "You are a technical writer. Based on the following git commit messages, "
                "create a concise bulleted summary of the main changes. Group related changes together "
                "and focus on the key technical updates. For the next period section, please "
                "look for clues in the past commits on what is coming up next. Don't mention past "
                "commits or past work or use the words potential or possible. Format exactly like this example. "
                "Condense the points from the commits, mentioning the high level changes only. Always condense "
                "to no more than 5 points per project even if there are more than 5. For the "
                "Next Period section, please use language like likely or may or potential or possible to "
                "suggest that something is coming up or might happen:\n\n"
                "-------------------------------------------\n"
                "Past Period (MM/DD/YY–MM/DD/YY)\n"
                "-------------------------------------------\n\n"
                "Project: Project Name 1\n\n"
                "    - Key accomplishment 1\n"
                "    - Key accomplishment 2\n\n"
                "Project: Project Name 2\n\n"
                "    - Key accomplishment 1\n"
                "    - Key accomplishment 2\n\n"
                "-------------------------------------------\n"
                "Next Period (MM/DD/YY–MM/DD/YY)\n"
                "-------------------------------------------\n\n"
                "Project: Project Name 1\n\n"
                "    - Key accomplishment 1\n"
                "    - Key accomplishment 2\n\n"
                "Project: Project Name 2\n\n"
                "    - Key accomplishment 1\n"
                "    - Key accomplishment 2\n\n"
                f"Use these date ranges:\n"
                f"Past Period: {start_date.strftime('%m/%d/%y')}–{end_date.strftime('%m/%d/%y')}\n"
                f"Next Period: {end_date.strftime('%m/%d/%y')}–{next_period_end.strftime('%m/%d/%y')}\n\n"
                f"Commit messages:\n{commit_text}"
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": instruction}],
                temperature=0.7,
            )
            summary = response.choices[0].message.content
            return summary.strip()
        except Exception as e:
            print(f"Error generating commit summary: {str(e)}")
            return "Error generating summary."

    def send_email(self, summary_text, recipients=None):
        """Send the commit summary via email."""
        if not recipients:
            raise ValueError("No recipients specified")

        def create_msg(sender, recipient_list):
            msg = MIMEText(summary_text)
            msg["Subject"] = f"Activity Update - {datetime.now().strftime('%Y-%m-%d')}"
            msg["From"] = sender
            msg["To"] = ", ".join(recipient_list)
            return msg

        # Always send emails from Gmail.
        gmail_email = os.getenv("GMAIL_EMAIL")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_email or not gmail_password:
            print("Warning: Gmail credentials are not configured")
            return False

        msg = create_msg(gmail_email, recipients)
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_email, gmail_password)
                server.send_message(msg)
                print(f"Email sent to: {msg['To']}")
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False


def main():
    try:
        parser = argparse.ArgumentParser(
            description="Track GitHub commits and generate summaries"
        )
        parser.add_argument(
            "-u", "--username", required=True, help="GitHub username to track"
        )
        parser.add_argument(
            "-tp",
            "--time_past",
            type=str,
            default="2w",
            help="Time offset for past activity, e.g., '2w', '14d', '1y'. Default: 2w",
        )
        parser.add_argument(
            "-tf",
            "--time_future",
            type=str,
            default="2w",
            help="Time offset for future activity, e.g., '2w', '10d', '1y'. Default: 2w",
        )
        parser.add_argument(
            "-e", "--email", nargs="+", help="Email recipients (optional)"
        )
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="Show detailed output"
        )
        parser.add_argument(
            "-d",
            "--display",
            action="store_true",
            help="Display summary in console",
        )
        args = parser.parse_args()

        past_offset = parse_time_delta(args.time_past)
        future_offset = parse_time_delta(args.time_future)

        tracker = CommitTracker(username=args.username)
        summary = tracker.generate_commit_summary(
            past_delta=past_offset, future_delta=future_offset
        )
        if args.email:
            tracker.send_email(summary, args.email)
        if args.display:
            print("\n=== Detailed Summary ===")
            print(summary)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

    print('--------------------------------')

    from datetime import timedelta

    tracker = CommitTracker(username="porwals")
    activity = tracker.get_activity(past_delta=timedelta(weeks=2), verbose=True)
    print("\n".join(activity))

    


