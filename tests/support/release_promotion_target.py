"""Finite process-backed GitHub release double for the local promotion probe."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _run() -> None:
    args = sys.argv[1:]
    path = Path(os.environ["COVERAGE_PILOT_PUBLICATION"])
    remote = os.environ["COVERAGE_PILOT_PUBLICATION_GIT"]
    repository = "jordanhubbard/literate-ai"
    tag = "v1.2.4"
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_bytes())
        release = state.get("release")
        asset = path.parent / "provider-asset"
        if args[:2] == ["api", "user"]:
            assert args[2:] == ["--jq", ".login", "--hostname", "github.com"]
            print(state.get("actor", "release-admin"))
        elif args[:3] == ["api", "--hostname", "github.com"] and "/git/" in args[-1]:
            heads = f"repos/{repository}/git/ref/heads/"
            if args[-1].startswith(heads):
                branch_ref = "refs/heads/" + args[-1][len(heads) :]
                branch = subprocess.check_output(
                    ["git", "-C", remote, "rev-parse", branch_ref], text=True
                ).strip()
                print(
                    json.dumps(
                        {"ref": branch_ref, "object": {"type": "commit", "sha": branch}}
                    )
                )
                return
            ref = f"refs/tags/{tag}"
            direct = subprocess.check_output(
                ["git", "-C", remote, "rev-parse", ref], text=True
            ).strip()
            if args[-1] == f"repos/{repository}/git/ref/tags/{tag}":
                print(
                    json.dumps({"ref": ref, "object": {"sha": direct, "type": "tag"}})
                )
            else:
                assert args[-1] == f"repos/{repository}/git/tags/{direct}"
                peeled = subprocess.check_output(
                    ["git", "-C", remote, "rev-parse", f"{ref}^{{}}"], text=True
                ).strip()
                print(
                    json.dumps(
                        {
                            "sha": direct,
                            "tag": tag,
                            "object": {
                                "type": "commit",
                                "sha": ("f" * 40 if state.get("wrong_tag") else peeled),
                            },
                        }
                    )
                )
        elif args[:2] == ["release", "view"]:
            assert args[2] == tag and args[3:5] == [
                "--repo",
                f"github.com/{repository}",
            ]
            if release is None:
                sys.exit("release not found")
            print(json.dumps(release))
        elif args[:2] == ["release", "create"]:
            assert args[2] == tag and args[3:5] == [
                "--repo",
                f"github.com/{repository}",
            ]
            assert "--draft" in args and "--verify-tag" in args and release is None
            state.setdefault("writes", []).append("draft")
            state["release"] = {
                "url": f"https://github.com/{repository}/releases/tag/{tag}",
                "databaseId": 501,
                "tagName": tag,
                "name": tag,
                "targetCommitish": args[args.index("--target") + 1],
                "isDraft": True,
                "isPrerelease": False,
                "body": Path(args[args.index("--notes-file") + 1]).read_text(),
                "assets": [],
            }
            if original := state.get("replace_original_after_staging"):
                source = Path(original)
                source.write_bytes(b"substituted after private staging")
        elif args[:5] == ["api", "--hostname", "github.com", "--method", "POST"]:
            src = Path(args[8])
            assert args[5:8] == [
                "--header",
                "Content-Type: application/octet-stream",
                "--input",
            ]
            assert args[9] == (
                f"https://uploads.github.com/repos/{repository}/releases/"
                f"{release['databaseId']}/assets?name={src.name}"
            )
            assert release["isDraft"] and not release["assets"]
            assert not src.is_relative_to(Path.cwd())
            assert (
                hashlib.sha256(src.read_bytes()).hexdigest()
                == state["expected_upload_digest"]
            )
            if state.get("alien_upload"):
                asset.write_bytes(b"concurrent alien state")
                content = asset.read_bytes()
            else:
                shutil.copyfile(src, asset)
                content = src.read_bytes()
            release["assets"] = [
                {
                    "name": src.name,
                    "id": "fixture-asset-655",
                    "size": len(content),
                    "state": "uploaded",
                    "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
                }
            ]
            state.setdefault("writes", []).append("attach")
            path.write_text(json.dumps(state))
            if state.get("lose_upload_reply") or state.get("alien_upload"):
                sys.exit("no success reply")
        elif args[:2] == ["release", "download"]:
            assert args[2] == tag and args[3:5] == [
                "--repo",
                f"github.com/{repository}",
            ]
            name = args[args.index("--pattern") + 1]
            assert len(release["assets"]) == 1 and release["assets"][0]["name"] == name
            shutil.copyfile(asset, Path(args[args.index("--dir") + 1]) / name)
        elif args[:5] == ["api", "--hostname", "github.com", "--method", "PATCH"]:
            assert args[5:] == [
                f"repos/{repository}/releases/{release['databaseId']}",
                "--field",
                "draft=false",
            ]
            assert release["isDraft"] and len(release["assets"]) == 1
            state.setdefault("writes", []).append("publish")
            release["isDraft"] = False
            path.write_text(json.dumps(state))
            if state.get("lose_publish_reply"):
                sys.exit("no success reply")
        else:
            sys.exit(f"unexpected stub command {args!r}")
        path.write_text(json.dumps(state))


if __name__ == "__main__":
    _run()
