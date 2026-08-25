import html
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

LOGIN = os.environ.get("GH_LOGIN", "AndreaMarangione")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT_DIR = "assets"
BG = "#1E1E1E"
BORDER = "#3A3A3A"
TITLE = "#E95420"
ICON = "#E95420"
TEXT = "#F5F5F5"
SANS = "Segoe UI, Ubuntu, sans-serif"
TOP_LANGS = 10
MAX_REPOS = 100

FIELDS = """
    name
    login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection(from: $from) {
      totalCommitContributions
      restrictedContributionsCount
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar { totalContributions }
    }
    repositoriesContributedTo(
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
    repositories(
      first: %d
      ownerAffiliations: OWNER
      isFork: false
      orderBy: { field: STARGAZERS, direction: DESC }
    ) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: { field: SIZE, direction: DESC }) {
          edges { size node { name color } }
        }
      }
    }
""" % MAX_REPOS

QUERY_PRIVATE = "query($from: DateTime!) { viewer {" + FIELDS + "} }"
QUERY_PUBLIC = "query($login: String!, $from: DateTime!) { user(login: $login) {" + FIELDS + "} }"

def fetch():
    personal = bool(os.environ.get("GH_TOKEN"))
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    if not token:
        sys.exit("ERRORE: manca il token (GH_TOKEN o GITHUB_TOKEN).")

    year_start = datetime(datetime.now(timezone.utc).year, 1, 1, tzinfo=timezone.utc)

    if personal:
        query = QUERY_PRIVATE
        variables = {"from": year_start.isoformat()}
    else:
        print("ATTENZIONE: GH_TOKEN assente, i repository privati non verranno conteggiati.")
        query = QUERY_PUBLIC
        variables = {"login": LOGIN, "from": year_start.isoformat()}

    payload = json.dumps({"query": query, "variables": variables}).encode()

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-stats-cards",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)

    if "errors" in body:
        sys.exit("ERRORE API: " + json.dumps(body["errors"], indent=2))

    data = body.get("data") or {}
    user = data.get("viewer") or data.get("user")

    if not user:
        sys.exit("ERRORE: utente non trovato o dati vuoti.")

    return user

def summarize(user):
    repos = user["repositories"]["nodes"]
    contrib = user["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in repos)
    sizes = {}
    colors = {}

    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            sizes[name] = sizes.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#858585"

    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:TOP_LANGS]
    shown = sum(v for _, v in ranked) or 1
    langs = [(n, round(v / shown * 100, 1), colors[n]) for n, v in ranked]

    return {
        "name": user.get("name") or LOGIN,
        "stars": stars,
        "commits": (contrib["totalCommitContributions"]
                    + contrib.get("restrictedContributionsCount", 0)),
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "langs": langs,
        "contrib": contrib,
    }

def rank(d):
    score = (
        d["commits"] * 1.0
        + d["prs"] * 3.0
        + d["issues"] * 2.0
        + d["stars"] * 4.0
        + d["followers"] * 2.0
        + d["contributed"] * 3.0
    )

    pct = 100 * (1 - math.exp(-score / 900))

    for limit, letter in ((90, "S"), (78, "A+"), (66, "A"), (54, "B+"),
                          (42, "B"), (28, "C+")):
        if pct >= limit:
            return letter, pct
    return "C", max(pct, 8)

def esc(t):
    return html.escape(str(t))

def txt(x, y, s, size=14, fill=TEXT, weight="normal", anchor="start", family=SANS):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

def icon(kind, x, y):
    c = ICON
    if kind == "star":
        return (f'<path transform="translate({x},{y}) scale(0.62)" fill="{c}" '
                'd="M8 .25l2.28 4.62 5.1.74-3.69 3.6.87 5.08L8 11.9l-4.56 2.39.87-5.08L.62 5.61l5.1-.74z"/>')
    if kind == "commit":
        return (f'<g transform="translate({x},{y}) scale(0.62)" fill="{c}">'
                '<path d="M10.86 7a3.5 3.5 0 0 0-6.72 0H1v2h3.14a3.5 3.5 0 0 0 6.72 0H15V7z"/>'
                f'<circle cx="7.5" cy="8" r="1.6" fill="{BG}"/></g>')
    if kind == "pr":
        return (f'<g transform="translate({x},{y}) scale(0.62)" fill="{c}">'
                '<circle cx="3.5" cy="3" r="2.4"/><circle cx="3.5" cy="13" r="2.4"/>'
                '<rect x="2.7" y="4" width="1.6" height="8"/>'
                '<circle cx="12.5" cy="13" r="2.4"/><rect x="11.7" y="4" width="1.6" height="8"/>'
                f'<path d="M4 3.5h6.5a2 2 0 0 1 2 2v1" stroke="{c}" stroke-width="1.6" fill="none"/></g>')
    if kind == "issue":
        return (f'<g transform="translate({x},{y}) scale(0.62)">'
                f'<circle cx="8" cy="8" r="6.6" fill="none" stroke="{c}" stroke-width="1.9"/>'
                f'<circle cx="8" cy="8" r="2.1" fill="{c}"/></g>')
    return (f'<g transform="translate({x},{y}) scale(0.62)" fill="{c}">'
            '<circle cx="8" cy="5" r="3.2"/><path d="M1.6 15c0-3.5 2.9-5.4 6.4-5.4s6.4 1.9 6.4 5.4z"/></g>')

def card_stats(d):
    W, H = 495, 195
    year = datetime.now(timezone.utc).year
    rows = [
        ("star", "Total Stars Earned", d["stars"]),
        ("commit", f"Total Commits ({year})", d["commits"]),
        ("pr", "Total PRs", d["prs"]),
        ("issue", "Total Issues", d["issues"]),
        ("person", "Contributed to", d["contributed"]),
    ]

    letter, pct = rank(d)

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" aria-label="Statistiche GitHub di {esc(d["name"])}">',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="6" fill="{BG}" stroke="{BORDER}"/>',
         txt(25, 35, f"{d['name']}'s GitHub Stats", 18, TITLE, "600")]

    for i, (kind, label, val) in enumerate(rows):
        y = 68 + i * 25
        s.append(icon(kind, 25, y - 11))
        s.append(txt(48, y, label, 14, TEXT))
        s.append(txt(320, y, f"{val:,}".replace(",", "."), 14, TEXT, "700"))

    cx, cy, r = 420, 105, 40
    circ = 2 * math.pi * r
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{BORDER}" stroke-width="6"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TITLE}" stroke-width="6" '
             f'stroke-linecap="round" stroke-dasharray="{circ*pct/100:.1f} {circ:.1f}" '
             f'transform="rotate(-90 {cx} {cy})"/>')
    s.append(txt(cx, cy + 9, letter, 26, TITLE, "700", "middle"))
    s.append('</svg>')
    return "\n".join(s)

def card_langs(d):
    W, H = 320, 195
    langs = d["langs"]

    l = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         'role="img" aria-label="Linguaggi più usati">',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="6" fill="{BG}" stroke="{BORDER}"/>',
         txt(25, 35, "Most Used Languages", 18, TITLE, "600")]

    bx, by, bw, bh = 25, 55, W - 50, 9
    l.append(f'<clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="4.5"/></clipPath>')

    off = bx
    for name, pct, col in langs:
        seg = bw * pct / 100
        l.append(f'<rect x="{off:.1f}" y="{by}" width="{seg+0.6:.1f}" height="{bh}" '
                 f'fill="{col}" clip-path="url(#bar)"/>')
        off += seg

    for i, (name, pct, col) in enumerate(langs):
        cx = 25 + (i % 2) * 148
        cy = 92 + (i // 2) * 26
        l.append(f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{col}"/>')
        l.append(txt(cx + 18, cy, name, 13, TEXT))
        l.append(txt(cx + 128, cy, f"{pct:.1f}%", 13, TEXT, anchor="end"))

    l.append('</svg>')
    return "\n".join(l)

def main():
    data = summarize(fetch())

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(f"{OUT_DIR}/stats.svg", "w", encoding="utf-8") as f:
        f.write(card_stats(data))
    with open(f"{OUT_DIR}/langs.svg", "w", encoding="utf-8") as f:
        f.write(card_langs(data))

    c = data["contrib"]
    print("commit                  :", c["totalCommitContributions"])
    print("commit privati nascosti :", c["restrictedContributionsCount"])
    print("issue                   :", c["totalIssueContributions"])
    print("pull request            :", c["totalPullRequestContributions"])
    print("review                  :", c["totalPullRequestReviewContributions"])
    print("totale grafico          :", c["contributionCalendar"]["totalContributions"])
    print("card generate:", {k: v for k, v in data.items() if k not in ("langs", "contrib")})
    print("linguaggi:", data["langs"])


if __name__ == "__main__":
    main()
