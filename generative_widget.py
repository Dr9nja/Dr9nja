#code from https://dev.to/iammastercraft/build-your-own-github-profile-widgets-from-scratch-2e3h#11-project-template
#edited by Dr9nja, 02.10.26
import os
import requests
from collections import defaultdict

USERNAME = os.environ.get("GITHUB_USERNAME", "your-username")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUTPUT = os.environ.get("OUTPUT_DIR", ".") 

def github_get(endpoint, params=None):
    headers = {"Accept": "application/vnd.github.v3+json"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    resp = requests.get(f"https://github.com{endpoint}",
                        headers=headers, params=params, timeout=30)
  
    return resp.json() if resp.status_code == 200 else {}

def fetch_data():
    user = github_get(f"/users/{USERNAME}")
    repos = github_get(f"/users/{USERNAME}/repos",
                       {"per_page": 100, "sort": "updated"})
    languages = defaultdict(int)
    for repo in (repos if isinstance(repos, list) else []):
        if not repo.get("fork"):
            langs = github_get(
                f"/repos/{USERNAME}/{repo['name']}/languages")
            for lang, count in langs.items():
                languages[lang] += count
    return {"user": user, "repos": repos, "languages": dict(languages)}

def generate_widget(data):
    width, height = 600, 120
    name = data["user"].get("name", USERNAME)
    repos = data["user"].get("public_repos", 0)
    followers = data["user"].get("followers", 0)

    return f'''<svg xmlns="http://w3.org" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" rx="12"
        fill="#fff" stroke="#e8e8ed" stroke-width="1"/>
  <text x="24" y="40" font-family="Arial, sans-serif"
        font-size="18" font-weight="600" fill="#1d1d1f">{name}</text>
  <text x="24" y="64" font-family="Arial, sans-serif"
        font-size="13" fill="#86868b">
    @{USERNAME} · {repos} repos · {followers} followers
  </text>
  <text x="24" y="96" font-family="Arial, sans-serif"
        font-size="12" fill="#aeaeb2">
    {len(data["languages"])} languages across all repositories
  </text>
</svg>
'''

if __name__ == "__main__":
    os.makedirs(OUTPUT, exist_ok=True)
    data = fetch_data()
    svg = generate_widget(data)
    path = os.path.join(OUTPUT, "my-widget.svg")
    with open(path, "w") as f:
        f.write(svg)
    print(f"Generated {path}")
