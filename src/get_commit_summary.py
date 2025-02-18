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
    def __init__(self, username, orgs=None, enterprise=False):
        # Load environment variables
        load_dotenv()
        self.username = username
        self.enterprise = enterprise
        if orgs is not None:
            self.orgs = orgs
        else:
            # If enterprise is enabled, use the enterprise orgs; otherwise, use personal orgs.
            if self.enterprise:
                self.orgs = ["Amplio", "Amplio-Projects"]
            else:
                self.orgs = [username, "juntotechnologies"]
        self.github = self._initialize_github()

    def _initialize_github(self):
        """Initialize GitHub connection with error handling"""
        load_dotenv()
        if self.enterprise:
            enterprise_url = os.getenv("GITHUB_ENTERPRISE_URL")
            if enterprise_url in [None, "", "your.enterprise.github.api.url"]:
                raise ValueError("Enterprise GitHub URL not configured correctly")
            token = os.getenv("GITHUB_ENTERPRISE_ACCESS_TOKEN", os.getenv("GITHUB_ACCESS_TOKEN"))
        else:
            enterprise_url = None
            token = os.getenv("GITHUB_ACCESS_TOKEN")
        
        if not token:
            raise ValueError("No GitHub access token found in environment variables")
        
        try:
            if self.enterprise:
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
                        commit_emails = {"shaun.porwal@gmail.com", "porwals@mskcc.org"}  # set of allowed emails
                        commits = [
                            commit for commit in all_commits
                            if commit.commit.author.email.lower() in commit_emails
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
                "commits or past work or use the words potential or possible. Format exactly like this example. "
                "Condense the points from the commits, mentioning the high level changes only. Always condense"
                " to no more than 5 points per project always no matter what if there are more than 5. For the "
                "Next Period section, please use language like likely or may or potential or possible to"
                " suggest that something is coming up or might happen:\n\n"
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
        if not recipients:
            raise ValueError("No recipients specified")

        def create_msg(sender, recipient_list):
            msg = MIMEText(summary_text)
            msg['Subject'] = f"Activity Update - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = sender
            msg['To'] = ", ".join(recipient_list)
            return msg

        # Always send emails from Gmail regardless of recipient domain.
        gmail_email = os.getenv("GMAIL_EMAIL")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_email or not gmail_password:
            print("Warning: Gmail credentials are not configured")
            return False

        msg = create_msg(gmail_email, recipients)
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(gmail_email, gmail_password)
                server.send_message(msg)
                print(f"Email sent to: {msg['To']}")
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
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
                        commit_emails = {"shaun.porwal@gmail.com", "porwals@mskcc.org"}  # set of allowed emails
                        commits = [
                            commit for commit in all_commits
                            if commit.commit.author.email.lower() in commit_emails
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
        parser.add_argument('--enterprise', action='store_true', help='Scan enterprise GitHub (MSKCC) for commits')
        args = parser.parse_args()
        tracker = CommitTracker(username=args.username, enterprise=args.enterprise)
        stats = tracker.get_detailed_stats(weeks_back=args.weeks_past)
        stats_text = tracker.format_stats_report(stats, weeks_back=args.weeks_past)
        summary = tracker.generate_commit_summary(weeks_past=args.weeks_past, weeks_future=args.weeks_future)
        if args.email:
            tracker.send_email(stats_text, summary, args.email)
        if args.display:
            print("\n=== Activity Statistics ===")
            print(stats_text)
            print("\n=== Detailed Summary ===")
            print(summary)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
