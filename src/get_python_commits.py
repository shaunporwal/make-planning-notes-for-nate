from github import Github


from dotenv import load_dotenv

load_dotenv()

access_token = os.getenv("GITHUB_ACCESS_TOKEN")
repo_name = "username/repo"  # Replace with your repo identifier

g = Github(access_token)
repo = g.get_repo(repo_name)
commits = repo.get_commits()

for commit in commits:
    print(commit.commit.message)
