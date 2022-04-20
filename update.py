import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from git import RemoteReference
from git.repo import Repo
from git.util import Actor


DIR = Path(__file__).parent


def checkout_and_pull(repo: Repo, branch: str | RemoteReference | None = None) -> None:
    repo.git.reset("--hard")
    repo.git.clean("-xdf")

    if not branch:
        branch = repo.remotes.origin.refs.HEAD.ref.remote_head
    elif isinstance(branch, RemoteReference):
        branch = branch.remote_head

    repo.git.checkout(branch)
    repo.git.pull()


def gh_actions_bot_commit(repo: Repo) -> None:
    if repo.is_dirty(untracked_files=True, submodules=True):
        repo.git.add(all=True)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        gh_actions_bot = Actor(
            "github-actions[bot]",
            "github-actions[bot]@users.noreply.github.com",
        )
        commit = repo.index.commit(now, author=gh_actions_bot, committer=gh_actions_bot)
        print(f'new commit "{commit.message}" {commit.hexsha}')
        repo.git.push()
        print("pushed")
    else:
        print("no changes")


def update(push: bool = False) -> None:
    yarn_repo = Repo(DIR / "yarn")
    yarn_repo.git.fetch()

    status: dict[str, str] = json.load(Path(DIR / "status.json").open())

    status_versions = [*status.keys()]
    def sort_by_version(ref: RemoteReference) -> int:
        if ref.remote_head in status_versions:
            return status_versions.index(ref.remote_head)
        else:
            return 9999
    
    for ref in sorted(yarn_repo.remotes.origin.refs, key=sort_by_version):
        if ref == yarn_repo.remotes.origin.refs.HEAD:
            continue

        branch_name: str = ref.remote_head
        branch_hash: str = ref.commit.hexsha

        print(branch_name, branch_hash)

        if branch_name not in status or status[branch_name] != branch_hash:
            checkout_and_pull(yarn_repo, branch_name)

            branch_dir = Path(DIR / "mappings" / branch_name)
            branch_dir.mkdir(exist_ok=True)

            shutil.copytree(Path(DIR / "yarn/mappings"), branch_dir, dirs_exist_ok=True)

            status[branch_name] = branch_hash

    checkout_and_pull(yarn_repo)
    json.dump(status, Path(DIR / "status.json").open("w"), indent=2)

    if push:
        print("pushing changes to github")
        gh_actions_bot_commit(yarn_repo)


if __name__ == "__main__":
    push = False
    if len(sys.argv) == 2:
        if sys.argv[1] == "push":
            push = True
    update(push)
