"""Create a GitHub repo and push this project. Requires GITHUB_TOKEN in the shell environment."""
from __future__ import annotations
import argparse, os, subprocess
from pathlib import Path
from github import Github
ROOT = Path(__file__).resolve().parent
def run(*args: str) -> None: subprocess.run(args, cwd=ROOT, check=True)
def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", default="kill-the-quote-spreadsheet"); parser.add_argument("--public", action="store_true")
    args = parser.parse_args(); token = os.getenv("GITHUB_TOKEN")
    if not token: raise SystemExit("Set GITHUB_TOKEN; never place it in source.")
    run("git", "init", "-b", "main"); run("git", "add", "."); run("git", "commit", "-m", "Initial procurement quote prototype")
    repo = Github(token).get_user().create_repo(args.repo, private=not args.public, auto_init=False)
    run("git", "remote", "add", "origin", repo.clone_url.replace("https://", f"https://x-access-token:{token}@")); run("git", "push", "-u", "origin", "main")
    print(repo.html_url)
if __name__ == "__main__": main()
