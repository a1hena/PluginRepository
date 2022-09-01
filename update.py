import json
import os
from datetime import datetime
from zipfile import ZipFile

PROVIDER = os.getenv(
    "PROVIDER", "https://raw.githubusercontent.com/a1hena/PluginRepository/master/dist")


def extract_manifests(env):
    manifests = {}
    for dirpath, _, filenames in os.walk(f"dist/{env}"):
        if "latest.zip" not in filenames:
            continue

        with ZipFile(f"{dirpath}/latest.zip") as z:
            plugin_name = dirpath.split("/")[-1]
            manifest = json.loads(z.read(f"{plugin_name}.json").decode())
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
        manifest["RepoUrl"] = get_repo_url(stable_path) or stable_manifest.get("RepoUrl")
        manifest["AssemblyVersion"] = stable_manifest["AssemblyVersion"]
        manifest["IsTestingExclusive"] = False
        manifest["LastUpdated"] = max(get_last_updated(stable_path))
        manifest["DownloadLinkInstall"] = stable_link
        manifest["Name"] = stable_manifest.get("Name") + " a1hena custom"
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
