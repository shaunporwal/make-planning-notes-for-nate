from github import Github
import os
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
import pytz
import ollama
import argparse
import smtplib
from email.mime.text import MIMEText
import socket

class CommitTracker:
    def __init__(self, username, orgs=None):
        self.username = username
        self.orgs = orgs or ["Amplio", "Amplio-Projects"]
        self.github = self._initialize_github()
        
    def _initialize_github(self):
        """Initialize GitHub connection with error handling"""
        load_dotenv()
        token = os.getenv("GITHUB_ACCESS_TOKEN")
        
        if not token:
            raise ValueError("No GitHub access token found in environment variables")
            
        try:
            enterprise_url = "https://github.mskcc.org/api/v3"
            g = Github(base_url=enterprise_url, login_or_token=token)
            # Test connection
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
                org = self.github.get_organization(org_name)
                repos = org.get_repos()
                
                for repo in repos:
                    try:
                        # Skip empty repositories silently
                        try:
                            repo.get_commits().get_page(0)
                        except Exception as e:
                            if "Git Repository is empty" in str(e):
                                continue
                            raise e
                        
                        # Check for commits
                        commits = repo.get_commits(author=self.username, since=start_date)
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
                        
                        if repo_commit_count > 0:
                            if verbose:
                                print(f"\nRepository: {repo.full_name}")
                                print(f"Found {repo_commit_count} commits")
                            all_activity.extend(repo_commits)
                            
                    except Exception as e:
                        print(f"Error accessing {repo.full_name}: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"Error accessing organization {org_name}: {str(e)}")
                continue
        
        if not all_activity and verbose:
            print("\nNo activity found in the specified time period.")
            
        return self._format_activity(all_activity)

    def _format_activity(self, commits):
        """Format commits by date for easy reporting"""
        # Sort commits by date
        commits.sort(key=lambda x: x['date'], reverse=True)
        
        # Group commits by date
        formatted_output = []
        current_date = None
        
        for commit in commits:
            commit_date = commit['date'].strftime('%Y-%m-%d')
            if commit_date != current_date:
                current_date = commit_date
                formatted_output.append(f"\n=== {commit_date} ===")
            
            formatted_output.append(
                f"[{commit['repo']}] {commit['message']}"
            )
        
        return formatted_output

    def generate_commit_summary(self, weeks_past=2, weeks_future=2):
        """Generate a bulleted summary of commits using Ollama."""
        try:
            # Get the raw commits first
            commits = self.get_activity(weeks_back=weeks_past)
            if not commits:
                return "No commits found in the specified time period."

            # Format commits into a single string
            commit_text = "\n".join(commits)

            # Calculate date ranges
            end_date = datetime.now()
            start_date = end_date - timedelta(weeks=weeks_past)
            next_period_end = end_date + timedelta(weeks=weeks_future)

            # Create the instruction for Ollama
            instruction = (
                "You are a technical writer. Based on the following git commit messages, "
                "create a concise bulleted summary of the main changes. Group related changes together "
                "and focus on the key technical updates. Format in markdown with these requirements:\n\n"
                f"Past {weeks_past} Week{'s' if weeks_past != 1 else ''} "
                f"({start_date.strftime('%m/%d/%y')}–{end_date.strftime('%m/%d/%y')}):\n"
                "__Past Period__\n"
                "- **Project Name**\n"
                "  - Key accomplishment 1\n"
                "  - Key accomplishment 2\n\n"
                f"Next {weeks_future} Week{'s' if weeks_future != 1 else ''} "
                f"({end_date.strftime('%m/%d/%y')}–{next_period_end.strftime('%m/%d/%y')}):\n"
                "__Next Period__\n"
                "- **Project Name**\n"
                "  - Planned task 1\n"
                "  - Planned task 2\n\n"
                "__Backburner__ (low priority):\n"
                "- **Project Name**:\n"
                "  - Future consideration 1\n"
                "  - Future consideration 2\n\n"
                f"Commit messages:\n{commit_text}"
            )

            # Initialize Ollama client
            import ollama
            ollama.BASE_URL = "http://localhost:11434"

            # Call the Ollama API
            response = ollama.chat(
                model='llama3.1:70b',
                messages=[{'role': 'user', 'content': instruction}],
                stream=True
            )
            
            stream = [chunk['message']['content'] for chunk in response]
            summary = "".join(stream)
            
            return summary.strip()

        except Exception as e:
            print(f"Error generating commit summary: {str(e)}")
            return "Error generating summary."

    def send_email(self, stats_text, summary_text, recipients=None):
        """Send the commit summary via MSK SMTP."""
        try:
            # MSK SMTP settings - using IP address instead of hostname
            smtp_servers = [
                ("outbound-smtp.mskcc.org", 25),
                ("10.35.0.47", 25),  # MSK SMTP IP address
                ("localhost", 25)
            ]
            sender_email = os.getenv("MSK_EMAIL")

            if not sender_email:
                raise ValueError("MSK email not found in environment variables")

            # Create message with plain text
            email_body = (
                f"{stats_text}\n\n"
                f"Development Summary\n"
                f"{'=' * 80}\n\n"
                f"{summary_text}"
            )
            
            msg = MIMEText(email_body)
            msg['Subject'] = f"Activity Update - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = sender_email
            msg['To'] = "; ".join(recipients) if recipients else sender_email

            # Try multiple SMTP configurations
            errors = []
            
            for smtp_server, smtp_port in smtp_servers:
                try:
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                        server.set_debuglevel(0)  # Disable debug output
                        server.send_message(msg)
                        print(f"Email sent to {msg['To']} successfully!")
                        return True
                except socket.gaierror as e:
                    errors.append(f"DNS resolution error for {smtp_server}")
                except ConnectionRefusedError as e:
                    errors.append(f"Connection refused by {smtp_server}")
                except Exception as e:
                    errors.append(f"Error with {smtp_server}")

            # If we get here, all attempts failed
            print("\nFailed to send email:")
            for error in errors:
                print(f"- {error}")
            return False

        except Exception as e:
            print(f"Error preparing email: {str(e)}")
            return False

    def get_detailed_stats(self, weeks_back=2):
        """Get detailed statistics for each organization and repository."""
        start_date = datetime.now(pytz.UTC) - timedelta(weeks=weeks_back)
        stats = {}
        
        for org_name in self.orgs:
            try:
                org = self.github.get_organization(org_name)
                stats[org_name] = {
                    'repos': {},
                    'total_commits': 0,
                    'total_issues': 0,
                    'total_comments': 0
                }
                
                for repo in org.get_repos():
                    try:
                        # Get commits
                        commits = repo.get_commits(author=self.username, since=start_date)
                        commit_count = sum(1 for _ in commits)
                        
                        # Get issues and comments
                        issues = repo.get_issues(creator=self.username, since=start_date, state='all')
                        issue_count = sum(1 for _ in issues)
                        
                        # Reset issues iterator and count comments
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
                            
                    except Exception as e:
                        print(f"Error accessing {repo.name}: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"Error accessing organization {org_name}: {str(e)}")
                continue
                
        return stats

    def format_stats_report(self, stats, weeks_back=2):
        """Format statistics into a concise text format."""
        from datetime import datetime, timedelta

        # Calculate date ranges
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks_back)
        date_range = f"({start_date.strftime('%m/%d/%y')}–{end_date.strftime('%m/%d/%y')})"
        
        output = [f"Activity Report {date_range}\n"]
        
        # Collect all repos with activity
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
            output.append("\nActive Repositories:")
            output.append(", ".join(active_repos))
            output.append(f"\nActivity Totals:")
            output.append(f"Commits: {total_commits}, Issues: {total_issues}, Comments: {total_comments}")
            output.append(f"Total Activity: {total_commits + total_issues + total_comments}")
        else:
            output.append("\nNo activity found in the specified time period.")
        
        return "\n".join(output)

def main():
    try:
        # Set up argument parser
        parser = argparse.ArgumentParser(description='Track GitHub commits and generate summaries')
        parser.add_argument('-u', '--username', required=True, help='GitHub username to track')
        parser.add_argument('-wp', '--weeks_past', type=int, default=2, help='Number of weeks to look back (default: 2)')
        parser.add_argument('-wf', '--weeks_future', type=int, default=2, help='Number of weeks to look forward (default: 2)')
        parser.add_argument('-e', '--email', nargs='+', help='Email recipients (optional)')
        parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')
        parser.add_argument('-d', '--display', action='store_true', help='Display activity table and summary in console')
        
        args = parser.parse_args()
        
        # Initialize tracker with provided username
        tracker = CommitTracker(username=args.username)
        
        # Get statistics and format as text table
        stats = tracker.get_detailed_stats(weeks_back=args.weeks_past)
        stats_text = tracker.format_stats_report(stats, weeks_back=args.weeks_past)
        
        # Get commit summary
        summary = tracker.generate_commit_summary(weeks_past=args.weeks_past, weeks_future=args.weeks_future)
        
        # Send email if recipients are provided
        if args.email:
            tracker.send_email(stats_text, summary, args.email)
        elif args.display:
            # Only print to console if --display flag is used
            print("\n=== Activity Statistics ===")
            print(stats_text)
            print("\n=== Detailed Summary ===")
            print(summary)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
