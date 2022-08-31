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


def merge_manifests(stable, testing):
    manifest_keys = set(list(stable.keys()) + list(testing.keys()))

    manifests = []
    for key in manifest_keys:
        stable_path = f"dist/stable/{key}"
        stable_manifest = stable.get(key, {})
        stable_link = f"{PROVIDER}/stable/{key}/latest.zip"
        testing_path = f"dist/testing/{key}"
        testing_manifest = testing.get(key, {})
        testing_link = f"{PROVIDER}/testing/{key}/latest.zip"

        manifest = testing_manifest.copy() if testing_manifest else stable_manifest.copy()

        manifest["Changelog"] = get_changelog(
            testing_path) or get_changelog(stable_path)
        manifest["IsHide"] = testing_manifest.get(
            "IsHide", stable_manifest.get("IsHide", False))
        manifest["RepoUrl"] = get_repo_url(testing_path) or get_repo_url(
            stable_path) or testing_manifest.get("RepoUrl", stable_manifest.get("RepoUrl"))
        manifest["AssemblyVersion"] = stable_manifest["AssemblyVersion"] if stable_manifest else testing_manifest["AssemblyVersion"]
        manifest["TestingAssemblyVersion"] = testing_manifest["AssemblyVersion"] if testing_manifest else None
        manifest["IsTestingExclusive"] = not bool(
            stable_manifest) and bool(testing_manifest)
        manifest["LastUpdated"] = max(get_last_updated(
            stable_path), get_last_updated(testing_path))
        manifest["DownloadLinkInstall"] = stable_link if stable_manifest else testing_link
        manifest["DownloadLinkTesting"] = testing_link if testing_manifest else stable_link
        # manifest["IconUrl"] = ""

        manifests.append(manifest)

    return manifests


def dump_master(manifests):
    manifests.sort(key=lambda x: x["InternalName"])

    with open("dist/pluginmaster.json", "w") as f:
        json.dump(manifests, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    stable = extract_manifests("stable")
    testing = extract_manifests("testing")

    manifests = merge_manifests(stable, testing)
    dump_master(manifests)
