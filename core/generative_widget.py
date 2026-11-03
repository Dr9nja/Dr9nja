#code from https://dev.to/iammastercraft/build-your-own-github-profile-widgets-from-scratch-2e3h#11-project-template
#edited by Dr9nja, 03.10.26-14.10.26
print("Version: 03.11.2026")

import os
import json
import requests
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import random
from urllib.parse import quote
import html
import base64
import mimetypes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

USERNAME = os.environ.get("GITHUB_USERNAME", "Dr9nja")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUTPUT = os.environ.get("OUTPUT_DIR", ".")
TARGET_DIR = os.environ.get(
    "TARGET_DIR",
    os.path.abspath(os.path.join(BASE_DIR, "..", "dist"))
)
PLACEHOLDERS_DIR = os.path.join(TARGET_DIR, "placeholder")


# ============================================================
# GitHub REST API
# ============================================================

def github_get(endpoint, params=None):
    headers = {
        "Accept": "application/vnd.github+json"
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    resp = requests.get(
        f"https://api.github.com{endpoint}",
        headers=headers,
        params=params,
        timeout=30
    )

    return resp.json() if resp.status_code == 200 else {}


# ============================================================
# GitHub GraphQL API
# Used for commits + contribution streak
# ============================================================

def github_graphql(query, variables=None):
    if not TOKEN:
        return {}

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    resp = requests.post(
        "https://api.github.com/graphql",
        headers=headers,
        json={
            "query": query,
            "variables": variables or {}
        },
        timeout=30
    )

    if resp.status_code != 200:
        return {}

    result = resp.json()

    if "errors" in result:
        print("GraphQL error:", result["errors"])
        return {}

    return result.get("data", {})


# ============================================================
# Fetch everything
# ============================================================

def fetch_data():

    # --------------------------------------------------------
    # Profile
    # --------------------------------------------------------

    user = github_get(f"/users/{USERNAME}")

    # --------------------------------------------------------
    # Repositories
    # --------------------------------------------------------

    repos = github_get(
        f"/users/{USERNAME}/repos",
        {
            "per_page": 100,
            "sort": "updated"
        }
    )

    # --------------------------------------------------------
    # Languages
    # --------------------------------------------------------

    languages = defaultdict(int)

    repos = repos if isinstance(repos, list) else []

    # count ALL repositories, including forks :P
    repo_count = len(repos)

    for repo in repos:

        langs = github_get(
            f"/repos/{USERNAME}/{repo['name']}/languages"
        )

        for lang, count in langs.items():
            languages[lang] += count

    # --------------------------------------------------------
    # Contributions
    # --------------------------------------------------------

    commits = 0
    streak = 0

    if TOKEN:

        year = datetime.now(timezone.utc).year

        query = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {

              totalCommitContributions

              contributionCalendar {
                weeks {
                  contributionDays {
                    date
                    contributionCount
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "login": USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z"
        }

        data = github_graphql(query, variables)

        try:

            contributions = (
                data["user"]["contributionsCollection"]
            )

            commits = contributions["totalCommitContributions"]

            # ------------------------------------------------
            # Flatten contribution calendar
            # ------------------------------------------------

            contribution_days = []

            for week in contributions["contributionCalendar"]["weeks"]:
                for day in week["contributionDays"]:
                    contribution_days.append(day)

            # Dates that have at least one contribution
            contribution_dates = {
                day["date"]
                for day in contribution_days
                if day["contributionCount"] > 0
            }

            # ------------------------------------------------
            # Calculate current streak
            # ------------------------------------------------

            today = datetime.now(timezone.utc).date()

            if today.isoformat() in contribution_dates:
                current_date = today

            elif (
                (today - timedelta(days=1)).isoformat()
                in contribution_dates
            ):
                current_date = today - timedelta(days=1)

            else:
                current_date = None

            if current_date:

                while current_date.isoformat() in contribution_dates:

                    streak += 1
                    current_date -= timedelta(days=1)

        except (KeyError, TypeError):

            commits = 0
            streak = 0

    return {
        "user": user,
        "repos": repos,
        "languages": dict(languages),
        "commits": commits,
        "streak": streak
    }


# ============================================================
# Generate SVG
# ============================================================

def generate_widget(data, theme="light"):

    width, height = 900, 290

    if theme == "dark":
        title_color = "#f0f6fc"
        stat_color = "#8b949e"
        lang_color = "#f0f6fc"
        pct_color = "#8b949e"
    else:
        title_color = "#1d1d1f"
        stat_color = "#57606a"
        lang_color = "#24292f"
        pct_color = "#57606a"

    # --------------------------------------------------------
    # User information
    # --------------------------------------------------------

    name = data["user"].get("name") or USERNAME

    repos = data["user"].get(
        "public_repos",
        0
    )

    commits = data.get(
        "commits",
        0
    )

    streak = data.get(
        "streak",
        0
    )

    languages = data.get(
        "languages",
        {}
    )

    # --------------------------------------------------------
    # Sort languages
    # --------------------------------------------------------

    sorted_languages = sorted(
        languages.items(),
        key=lambda item: item[1],
        reverse=True
    )

    top_languages = sorted_languages[:9]

    total = sum(
        count
        for _, count in top_languages
    )

    language_data = []

    for language, count in top_languages:

        percentage = (
            count / total * 100
            if total
            else 0
        )

        language_data.append(
            (language, percentage)
        )

    # --------------------------------------------------------
    # Language colors from colors.json
    # --------------------------------------------------------

    colors_path = os.path.join(BASE_DIR, "colors.json")

    try:
        with open(colors_path, "r", encoding="utf-8") as f:
            color_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load {colors_path}: {e}")
        color_data = {}

    def get_color(lang_name):
        return (color_data.get(lang_name) or {}).get("color") or "#000000"

    colors = [
        get_color(language)
        for language, _ in language_data
    ]

    # --------------------------------------------------------
    # Random cat word
    # --------------------------------------------------------

    words_path = os.path.join(BASE_DIR, "cat-api_words.json")

    try:
        with open(words_path, "r", encoding="utf-8") as f:
            word_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load {words_path}: {e}")
        word_data = {"Words": []}

    def get_word():
        words = word_data.get("Words", [])

        if not words:
            return "Cat"

        return random.choice(words)

    # --------------------------------------------------------
    # Cataas image (with local placeholder fallback)
    # --------------------------------------------------------

    random_text = get_word()

    cat_url = (
        f"hhttps://cataas.com/cat/says/{quote(random_text)}"
        f"?fontSize=65&fontColor=white&random={random.randint(1, 999999999)}"
    )

    cat_image = ""
    image_base64 = None
    image_type = "image/jpeg"
    failed_to_load = False

    # Try the online cat first
    try:
        response = requests.get(cat_url, timeout=30)
        response.raise_for_status()

        image_base64 = base64.b64encode(
            response.content
        ).decode("utf-8")

        image_type = response.headers.get(
            "Content-Type", "image/jpeg"
        )

    except requests.RequestException as e:
        print(f"Could not fetch cat image: {e}")
        failed_to_load = True

    # Fall back to a local placeholder ONLY if the download failed
    if failed_to_load:
        try:
            if os.path.isdir(PLACEHOLDERS_DIR):
                local_images = [
                    f for f in os.listdir(PLACEHOLDERS_DIR)
                    if os.path.isfile(os.path.join(PLACEHOLDERS_DIR, f))
                ]
            else:
                local_images = []

            if local_images:
                random_image_name = random.choice(local_images)
                image_path = os.path.join(PLACEHOLDERS_DIR, random_image_name)

                image_type = (
                    mimetypes.guess_type(random_image_name)[0]
                    or "image/jpeg"
                )

                with open(image_path, "rb") as img_file:
                    image_base64 = base64.b64encode(
                        img_file.read()
                    ).decode("utf-8")

                failed_to_load = False
            else:
                print("No images found in placeholders directory.")

        except Exception as e:
            print(f"Could not load local cat image: {e}")

    if not failed_to_load and image_base64:
        cat_image = f'''
  <image
    x="600"
    y="65"
    width="280"
    height="210"
    href="data:{image_type};base64,{image_base64}"
    preserveAspectRatio="xMidYMid slice"
  />
'''

    # --------------------------------------------------------
    # Progress bar
    # --------------------------------------------------------

    bar_x = 24
    bar_y = 80
    bar_width = 552

    progress_bar = []

    current_x = bar_x

    for (_, percentage), color in zip(
        language_data,
        colors
    ):

        segment_width = (
            bar_width * percentage / 100
        )

        if segment_width > 0:

            progress_bar.append(
                f'''
    <rect
      x="{current_x:.2f}"
      y="{bar_y}"
      width="{segment_width:.2f}"
      height="10"
      fill="{color}"
    />'''
            )

        current_x += segment_width

    # --------------------------------------------------------
    # Legend
    # --------------------------------------------------------

    positions = [
        (24, 125),
        (210, 125),
        (390, 125),
        (24, 160),
        (210, 160),
        (390, 160),
        (24, 195),
        (210, 195),
        (390, 195)
    ]

    legend = []

    for (
        (language, percentage),
        color,
        (x, y)
    ) in zip(
        language_data,
        colors,
        positions
    ):

        legend.append(
            f'''
  <g transform="translate({x}, {y})">
    <circle
      cx="5"
      cy="-5"
      r="5"
      fill="{color}"
    />

    <text
      x="18"
      y="0"
      class="lang-text"
    >
      {html.escape(language)}
      <tspan class="pct-text">
        {percentage:.1f}%
      </tspan>
    </text>
  </g>
'''
        )

    # --------------------------------------------------------
    # SVG
    # --------------------------------------------------------

    return f'''
<svg
  xmlns="http://www.w3.org/2000/svg"
  width="{width}"
  height="{height}"
  viewBox="0 0 {width} {height}"
>

  <style>

    .title {{
      font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Helvetica,
        Arial,
        sans-serif;

      font-size: 18px;
      font-weight: 600;
      fill: {title_color};
    }}

    .stat-text {{
      font-family:
        ui-monospace,
        SFMono-Regular,
        SF Mono,
        Menlo,
        Consolas,
        monospace;

      font-size: 13px;
      fill: {stat_color};
    }}

    .lang-text {{
      font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Helvetica,
        Arial,
        sans-serif;

      font-size: 13px;
      font-weight: 500;
      fill: {lang_color};
    }}

    .pct-text {{
      font-family:
        ui-monospace,
        SFMono-Regular,
        SF Mono,
        Menlo,
        Consolas,
        monospace;

      font-size: 12px;
      fill: {pct_color};
    }}

  </style>

  <!-- Header Info -->

  <text
    x="24"
    y="36"
    class="title"
  >
    My most used languages 💚🖤
  </text>

  <text
    x="24"
    y="58"
    class="stat-text"
  >
    @{USERNAME} · {repos} repos · {commits} commits · {streak} streak in days
  </text>

  <!-- Multi-Color Progress Bar -->

  <g id="progress-bar">
    {''.join(progress_bar)}
  </g>

  <!-- Legend -->

  {''.join(legend)}

  <!-- Cat of the Hour -->

  <text
    x="600"
    y="40"
    class="title"
  >
    Cat of the hour!
  </text>

  {cat_image}

</svg>
'''


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    os.makedirs(OUTPUT, exist_ok=True)
    os.makedirs(TARGET_DIR, exist_ok=True)

    data = fetch_data()

    # --------------------------------------------------------
    # Generate light theme SVG
    # --------------------------------------------------------

    light_svg = generate_widget(
        data,
        theme="light"
    )

    light_path = os.path.join(
        TARGET_DIR,
        "my-widget-light.svg"
    )

    with open(
        light_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(light_svg)

    print(f"Generated {light_path}")

    # --------------------------------------------------------
    # Generate dark theme SVG
    # --------------------------------------------------------

    dark_svg = generate_widget(
        data,
        theme="dark"
    )

    dark_path = os.path.join(
        TARGET_DIR,
        "my-widget-dark.svg"
    )

    with open(
        dark_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(dark_svg)

    print(f"Generated {dark_path}")
