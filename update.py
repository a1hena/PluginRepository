import json
import os
from datetime import datetime
from zipfile import ZipFile
from pprint import pprint
from pathlib import Path
PROVIDER = os.getenv(
    "PROVIDER", "https://raw.githubusercontent.com/a1hena/PluginRepository/master/dist")


def extract_manifests(env):
    manifests = {}
    env_path = (Path("dist") / env )
    for dirpath in env_path.iterdir():

        plugin_name = dirpath.name
        if not (env_path/plugin_name/ f"{plugin_name}.json").exists():
            continue
        pprint(plugin_name)
        with open(f"{dirpath}/{plugin_name}.json") as f:
            manifest = json.load(f)
            manifests[manifest["InternalName"]] = manifest

    return manifests


def get_changelog(path):
    commits_path = f"{path}/commits.json"
    if not os.path.exists(commits_path):
        return None

    with open(commits_path) as f:
        commits = json.load(f)

    if not isinstance(commits, list):
        return None

    return "\n".join([
        f"{x['sha'][:7]}: {x['commit']['message']}"
        for x in commits
        if x["commit"]["author"]["name"] != "github-actions"
    ]) or None


def get_repo_url(path):
    event_path = f"{path}/event.json"
    if not os.path.exists(event_path):
        return None

    with open(event_path) as f:
        event = json.load(f)

    if "repository" in event:
        return event["repository"]["html_url"]

    return None


def get_last_updated(path):
    event_path = f"{path}/event.json"
    if not os.path.exists(event_path):
        zip_path = f"{path}/latest.zip"
        if not os.path.exists(zip_path):
            return 0

        return int(os.path.getmtime(zip_path))

    with open(event_path) as f:
        event = json.load(f)

    # on: push
    if "head_commit" in event:
        timestamp = event["head_commit"]["timestamp"]
    # on: release
    elif "created_at" in event:
        timestamp = event["created_at"]
    # on: workflow_dispatch
    else:
        commits_path = f"{path}/commits.json"
        with open(commits_path) as f:
            commits = json.load(f)
        timestamp = commits[0]["commit"]["author"]["date"]

    try:
        epoch = datetime.fromisoformat(timestamp)
    except ValueError:
        epoch = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    return int(epoch.timestamp())


def merge_manifests(stable):
    manifest_keys = set(list(stable.keys()))

    manifests = []
    for key in manifest_keys:
        stable_path = f"dist/stable/{key}"
        stable_manifest = stable.get(key, {})
        stable_link = f"{PROVIDER}/stable/{key}/latest.zip"

        manifest = stable_manifest.copy()

        manifest["Changelog"] = get_changelog(stable_path)
        manifest["IsHide"] = False
        manifest["RepoUrl"] = get_repo_url(
            stable_path) or stable_manifest.get("RepoUrl")
        manifest["AssemblyVersion"] = stable_manifest["AssemblyVersion"]
        manifest["IsTestingExclusive"] = False
        manifest["LastUpdated"] = get_last_updated(stable_path)
        manifest["DownloadLinkInstall"] = stable_link
        manifest["Name"] = stable_manifest.get("Name") + " a1hena custom"
        manifest["Author"] = stable_manifest.get("Author") + ", a1hena"
        manifest["InternalName"] = stable_manifest.get("InternalName") + " a1hena custom"

        manifests.append(manifest)

    return manifests


def dump_master(manifests):
    manifests.sort(key=lambda x: x["InternalName"])

    with open("dist/pluginmaster.json", "w") as f:
        json.dump(manifests, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    stable = extract_manifests("stable")
    manifests = merge_manifests(stable)
    dump_master(manifests)
