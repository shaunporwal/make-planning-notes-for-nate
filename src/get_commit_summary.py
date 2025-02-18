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

dotenv_path = os.path.join(os.path.dirname(__file__), '../.env')  # adjust as needed
load_dotenv(dotenv_path)

class CommitTracker:
    def __init__(self, username, orgs=None):
        # Load environment variables
        load_dotenv()
        self.username = username
        
        # Check for enterprise settings – treat placeholder or empty as not set
        enterprise_url = os.getenv("GITHUB_ENTERPRISE_URL")
        if enterprise_url in [None, "", "your.enterprise.github.api.url"]:
            enterprise_url = None

        # Set default organizations if none provided: 
        # * For enterprise, use the team repos ("Amplio", "Amplio-Projects")
        # * For public GitHub, use the user's account and "juntotechnologies"
        if orgs is None:
            if enterprise_url:
                self.orgs = ["Amplio", "Amplio-Projects"]
            else:
                self.orgs = [username, "juntotechnologies"]
        else:
            self.orgs = orgs

        self.github = self._initialize_github()

    def _initialize_github(self):
        """Initialize GitHub connection with error handling"""
        load_dotenv()
        enterprise_url = os.getenv("GITHUB_ENTERPRISE_URL")
        if enterprise_url in [None, "", "your.enterprise.github.api.url"]:
            enterprise_url = None

        # In enterprise mode, try to get the enterprise token; fallback to GITHUB_ACCESS_TOKEN if needed.
        if enterprise_url:
            token = os.getenv("GITHUB_ENTERPRISE_ACCESS_TOKEN", os.getenv("GITHUB_ACCESS_TOKEN"))
        else:
            token = os.getenv("GITHUB_ACCESS_TOKEN")
        
        if not token:
            raise ValueError("No GitHub access token found in environment variables")
        
        try:
            if enterprise_url:
                g = Github(base_url=enterprise_url, login_or_token=token)
            else:
                g = Github(token)
            # Test the connection
            g.get_user()
            return g
        except Exception as e:
            raise ConnectionError(f"Failed to connect to GitHub: {str(e)}")

    def get_activity(self, weeks_back=2, verbose=False):
        """Get all GitHub activity from specified weeks back until now"""
        start_date = datetime.now(pytz.UTC) - timedelta(weeks=weeks_back)
        all_activity = []
        
        if verbose:
            print(f"\n=== Fetching Activity Since {start_date.strftime('%Y-%m-%d')} ===")
        
        for org_name in self.orgs:
            try:
                # If the org name matches the username then retrieve user repos.
                if org_name.lower() == self.username.lower():
                    entity = self.github.get_user(org_name)
                else:
                    entity = self.github.get_organization(org_name)
                repos = entity.get_repos()
                
                for repo in repos:
                    try:
                        # Skip empty repositories silently
                        try:
                            repo.get_commits().get_page(0)
                        except Exception:
                            continue
                        
                        # Get commits authored by the username since the start date.
                        all_commits = repo.get_commits(since=start_date)
                        commits = [
                            commit for commit in all_commits
                            if commit.commit.author.email.lower() == "shaun.porwal@gmail.com"
                        ]
                        repo_commit_count = 0
                        repo_commits = []
                        
                        for commit in commits:
                            commit_date = commit.commit.author.date
                            if commit_date.tzinfo is None:
                                commit_date = pytz.UTC.localize(commit_date)
                            
                            if commit_date >= start_date:
                                repo_commit_count += 1
                                repo_commits.append({
                                    'date': commit_date,
                                    'repo': repo.full_name,
                                    'message': commit.commit.message.splitlines()[0]
                                })
                            
                            if verbose:
                                print(f"Repo: {repo.full_name} | Commit: {commit.commit.message.splitlines()[0]}")
                                print(f"   Author: {commit.commit.author.name}, Email: {commit.commit.author.email} | Date: {commit_date}")
                        
                        if repo_commit_count > 0:
                            if verbose:
                                print(f"\nRepository: {repo.full_name}")
                                print(f"Found {repo_commit_count} commits")
                            all_activity.extend(repo_commits)
                            
                    except Exception as e:
                        if verbose:
                            print(f"Error accessing {repo.full_name}: {str(e)}")
                        continue
                        
            except Exception as e:
                if verbose:
                    print(f"Error accessing organization/account {org_name}: {str(e)}")
                continue
        
        if not all_activity and verbose:
            print("\nNo activity found in the specified time period.")
            
        return self._format_activity(all_activity)

    def _format_activity(self, commits):
        """Format commits by date for easy reporting"""
        commits.sort(key=lambda x: x['date'], reverse=True)
        formatted_output = []
        current_date = None
        
        for commit in commits:
            commit_date = commit['date'].strftime('%Y-%m-%d')
            if commit_date != current_date:
                current_date = commit_date
                formatted_output.append(f"\n=== {commit_date} ===")
            formatted_output.append(f"[{commit['repo']}] {commit['message']}")
        
        return formatted_output

    def generate_commit_summary(self, weeks_past=2, weeks_future=2):
        """Generate a bulleted summary of commits using OpenAI."""
        try:
            commits = self.get_activity(weeks_back=weeks_past)
            if not commits:
                return "No commits found in the specified time period."
            commit_text = "\n".join(commits)
            end_date = datetime.now()
            start_date = end_date - timedelta(weeks=weeks_past)
            next_period_end = end_date + timedelta(weeks=weeks_future)
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            instruction = (
                "You are a technical writer. Based on the following git commit messages, "
                "create a concise bulleted summary of the main changes. Group related changes together "
                "and focus on the key technical updates. For the next period section, please "
                "look for clues in the past commits on what is coming up next. Don't mention past "
                "commits or past work or use the words potential or possible. Format exactly like this example:\n\n"
                "Past Period (MM/DD/YY–MM/DD/YY)\n\n"
                "- Project Name 1\n\n"
                "  - Key accomplishment 1\n"
                "  - Key accomplishment 2\n\n"
                "- Project Name 2\n\n"
                "  - Key accomplishment 1\n"
                "  - Key accomplishment 2\n\n"
                "Next Period (MM/DD/YY–MM/DD/YY)\n\n"
                "- Project Name 1\n\n"
                "  - Key accomplishment 1\n"
                "  - Key accomplishment 2\n\n"
                "- Project Name 2\n\n"
                "  - Key accomplishment 1\n"
                "  - Key accomplishment 2\n\n"
                f"Use these date ranges:\n"
                f"Past Period: {start_date.strftime('%m/%d/%y')}–{end_date.strftime('%m/%d/%y')}\n"
                f"Next Period: {end_date.strftime('%m/%d/%y')}–{next_period_end.strftime('%m/%d/%y')}\n\n"
                f"Commit messages:\n{commit_text}"
            )
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{'role': 'user', 'content': instruction}],
                temperature=0.7
            )
            summary = response.choices[0].message.content
            return summary.strip()
        except Exception as e:
            print(f"Error generating commit summary: {str(e)}")
            return "Error generating summary."

    def send_email(self, stats_text, summary_text, recipients=None):
        """Send the commit summary via email."""
        try:
            if not recipients:
                raise ValueError("No recipients specified")
            msk_recipients = [r for r in recipients if "@mskcc.org" in r.lower()]
            external_recipients = [r for r in recipients if "@mskcc.org" not in r.lower()]
            all_success = True

            def create_msg(sender, recipient_list):
                msg = MIMEText(summary_text)
                msg['Subject'] = f"Activity Update - {datetime.now().strftime('%Y-%m-%d')}"
                msg['From'] = sender
                msg['To'] = ", ".join(recipient_list)
                return msg

            msk_email = os.getenv("MSK_EMAIL")
            if msk_recipients and msk_email:
                smtp_servers = [
                    (os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT", "25"))),
                    (os.getenv("SMTP_SERVER_IP"), int(os.getenv("SMTP_PORT", "25"))),
                    ("localhost", 25)
                ]
                msg = create_msg(msk_email, msk_recipients)
                sent = False
                errors = []
                for smtp_server, smtp_port in smtp_servers:
                    try:
                        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                            server.send_message(msg)
                            print(f"Email sent to MSK recipients: {msg['To']}")
                            sent = True
                            break
                    except Exception as e:
                        errors.append(f"Error with {smtp_server}: {str(e)}")
                if not sent:
                    print("Failed to send to MSK recipients:")
                    for error in errors:
                        print(f" - {error}")
                    all_success = False
            elif msk_recipients:
                external_recipients.extend(msk_recipients)
            if external_recipients:
                gmail_email = os.getenv("GMAIL_EMAIL")
                gmail_password = os.getenv("GMAIL_APP_PASSWORD")
                if gmail_email and gmail_password:
                    msg = create_msg(gmail_email, external_recipients)
                    try:
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                            server.login(gmail_email, gmail_password)
                            server.send_message(msg)
                            print(f"Email sent to external recipients: {msg['To']}")
                    except Exception as e:
                        print(f"Error sending to external recipients: {str(e)}")
                        all_success = False
                else:
                    print("Warning: Cannot send to external recipients - Gmail credentials not configured")
                    all_success = False
            return all_success
        except Exception as e:
            print(f"Error preparing email: {str(e)}")
            return False

    def get_detailed_stats(self, weeks_back=2):
        """Get detailed statistics for each organization and repository."""
        start_date = datetime.now(pytz.UTC) - timedelta(weeks=weeks_back)
        stats = {}
        for org_name in self.orgs:
            try:
                if org_name.lower() == self.username.lower():
                    entity = self.github.get_user(org_name)
                else:
                    entity = self.github.get_organization(org_name)
                stats[org_name] = {
                    'repos': {},
                    'total_commits': 0,
                    'total_issues': 0,
                    'total_comments': 0
                }
                for repo in entity.get_repos():
                    try:
                        try:
                            repo.get_commits().get_page(0)
                        except:
                            continue
                        all_commits = repo.get_commits(since=start_date)
                        commits = [
                            commit for commit in all_commits
                            if commit.commit.author.email.lower() == "shaun.porwal@gmail.com"
                        ]
                        commit_count = sum(1 for _ in commits)
                        issues = repo.get_issues(creator=self.username, since=start_date, state='all')
                        issue_count = sum(1 for _ in issues)
                        issues = repo.get_issues(creator=self.username, since=start_date, state='all')
                        comment_count = sum(
                            1 for issue in issues 
                            for comment in issue.get_comments() 
                            if comment.user.login == self.username and comment.created_at >= start_date
                        )
                        if commit_count + issue_count + comment_count > 0:
                            stats[org_name]['repos'][repo.name] = {
                                'commits': commit_count,
                                'issues': issue_count,
                                'comments': comment_count
                            }
                            stats[org_name]['total_commits'] += commit_count
                            stats[org_name]['total_issues'] += issue_count
                            stats[org_name]['total_comments'] += comment_count
                    except:
                        continue
            except:
                continue
        return stats

    def format_stats_report(self, stats, weeks_back=2):
        """Format statistics into a concise text format."""
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks_back)
        date_range = f"({start_date.strftime('%m/%d/%y')}–{end_date.strftime('%m/%d/%y')})"
        output = [f"Activity Report {date_range}\n"]
        active_repos = []
        total_commits = 0
        total_issues = 0
        total_comments = 0
        for org_name, org_data in stats.items():
            for repo_name, repo_data in org_data['repos'].items():
                if repo_data['commits'] + repo_data['issues'] + repo_data['comments'] > 0:
                    active_repos.append(f"{org_name}/{repo_name}")
                    total_commits += repo_data['commits']
                    total_issues += repo_data['issues']
                    total_comments += repo_data['comments']
        if active_repos:
            output.append("Active Repositories:\n")
            output.extend(active_repos)
            output.append(f"\nActivity Totals:\n")
            output.append(f"Commits: {total_commits}")
            output.append(f"Issues: {total_issues}")
            output.append(f"Comments: {total_comments}")
            output.append(f"Total Activity: {total_commits + total_issues + total_comments}")
        else:
            output.append("\nNo activity found in the specified time period.")
        return "\n".join(output)

def main():
    try:
        parser = argparse.ArgumentParser(description='Track GitHub commits and generate summaries')
        parser.add_argument('-u', '--username', required=True, help='GitHub username to track')
        parser.add_argument('-wp', '--weeks_past', type=int, default=2, help='Number of weeks to look back (default: 2)')
        parser.add_argument('-wf', '--weeks_future', type=int, default=2, help='Number of weeks to look forward (default: 2)')
        parser.add_argument('-e', '--email', nargs='+', help='Email recipients (optional)')
        parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')
        parser.add_argument('-d', '--display', action='store_true', help='Display activity table and summary in console')
        args = parser.parse_args()
        tracker = CommitTracker(username=args.username)
        stats = tracker.get_detailed_stats(weeks_back=args.weeks_past)
        stats_text = tracker.format_stats_report(stats, weeks_back=args.weeks_past)
        summary = tracker.generate_commit_summary(weeks_past=args.weeks_past, weeks_future=args.weeks_future)
        if args.email:
            tracker.send_email(stats_text, summary, args.email)
        elif args.display:
            print("\n=== Activity Statistics ===")
            print(stats_text)
            print("\n=== Detailed Summary ===")
            print(summary)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
