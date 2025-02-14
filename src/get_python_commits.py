from github import Github
import os
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
import pytz
import ollama

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

    def get_activity(self, weeks_back=2):
        """Get all GitHub activity from specified weeks back until now"""
        start_date = datetime.now(pytz.UTC) - timedelta(weeks=weeks_back)
        all_activity = []
        
        print(f"\n=== Fetching Activity Since {start_date.strftime('%Y-%m-%d')} ===")
        
        for org_name in self.orgs:
            print(f"\nChecking organization: {org_name}")
            try:
                org = self.github.get_organization(org_name)
                repos = org.get_repos()
                
                for repo in repos:
                    try:
                        # Skip empty repositories
                        try:
                            repo.get_commits().get_page(0)
                        except Exception as e:
                            if "Git Repository is empty" in str(e):
                                continue
                            raise e
                        
                        # Check for commits before printing repository name
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
                        
                        # Only print repository info if commits were found
                        if repo_commit_count > 0:
                            print(f"\nRepository: {repo.full_name}")
                            print(f"Found {repo_commit_count} commits")
                            all_activity.extend(repo_commits)
                            
                    except Exception as e:
                        print(f"Error accessing {repo.full_name}: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"Error accessing organization {org_name}: {str(e)}")
                continue
        
        if not all_activity:
            print("\nNo activity found in the specified time period.")
            return []
            
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

    def generate_commit_summary(self, weeks_back=2):
        """Generate a bulleted summary of commits using Ollama."""
        try:
            # Get the raw commits first
            commits = self.get_activity(weeks_back=weeks_back)
            if not commits:
                return "No commits found in the specified time period."

            # Format commits into a single string
            commit_text = "\n".join(commits)

            # Initialize Ollama client
            import ollama
            ollama.BASE_URL = "http://localhost:11434"

            # Create the instruction for Ollama
            instruction = (
                "You are a technical writer. Based on the following git commit messages, "
                "create a concise bulleted summary of the main changes. Group related changes together "
                "and focus on the key technical updates. Format in markdown. Put it in this format:\n\n"
                "Past 2 Weeks (MM/DD/YY–MM/DD/YY):\n"
                "- Project Name\n"
                "  - Key accomplishment 1\n"
                "  - Key accomplishment 2\n\n"
                "Next 2 Weeks (MM/DD/YY–MM/DD/YY):\n"
                "- Project Name\n"
                "  - Planned task 1\n"
                "  - Planned task 2\n\n"
                "Backburner (low priority):\n"
                "- Project Name:\n"
                "  - Future consideration 1\n"
                "  - Future consideration 2\n\n"
                f"Commit messages:\n{commit_text}"
            )

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

def main():
    try:
        # Initialize tracker
        tracker = CommitTracker(username="porwals")
        
        # Get weeks from command line argument
        weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 2
        
        # Get both detailed commits and summary
        print("\n=== Detailed Commit Log ===")
        commits = tracker.get_activity(weeks_back=weeks)
        for line in commits:
            print(line)
            
        print("\n=== Summary of Changes ===")
        summary = tracker.generate_commit_summary(weeks_back=weeks)
        print(summary)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
