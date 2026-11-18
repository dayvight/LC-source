#!/usr/bin/env python3
"""
Rebuild the AltStore / LiveContainer source for this repo.

Reads apps.txt (one app per line: "<Name> <owner/repo>" plus optional
bundle id, min iOS version and tint colour), pulls each project's GitHub
releases, and rewrites:

  apps/<Name>/apps.json         per-app source
  apps/<Name>/apps-proxy.json   same, with gh-proxy mirrored asset URLs
  all-apps.json                 combined source
  all-apps-proxy.json           combined source, gh-proxy mirrored

Metadata (subtitle, description, developer, icon) is kept in
apps/<Name>/meta.json — edit that file, not the generated sources.

Run locally:   GITHUB_TOKEN=xxx python3 scripts/build_source.py
In Actions:   the token is provided automatically.
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

OWNER_REPO = os.environ.get("SOURCE_REPO", "").strip()  # e.g. "dayvight/LC-source"
BRANCH = os.environ.get("SOURCE_BRANCH", "main")
# Mirror used by the *-proxy.json sources. These services come and go, so it is
# overridable: set GH_PROXY=https://<mirror>/ when the default stops working.
PROXY = os.environ.get("GH_PROXY", "https://ghproxy.net/")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_VERSIONS = int(os.environ.get("MAX_VERSIONS", "5"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def raw_url(path=""):
    base = f"https://raw.githubusercontent.com/{OWNER_REPO}/refs/heads/{BRANCH}"
    return f"{base}/{path}" if path else base


RELEASE_DOWNLOAD_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+/releases/download/")


def proxify(url):
    """Mirror asset URLs through gh-proxy.

    Only real file URLs are rewritten: raw assets and release downloads. The
    second case matters most — the IPA is the largest thing the client fetches,
    so a proxy build that left it pointing at github.com would break on exactly
    the network the proxy exists for. Browsable pages (repo website) are left
    alone.
    """
    if url.startswith("https://raw.githubusercontent.com/") or RELEASE_DOWNLOAD_RE.match(url):
        return PROXY + url
    return url


def api_json(url):
    """Fetch via curl: the Python urllib in some sandboxes truncates large responses."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        cmd = ["curl", "-sfL", "--retry", "3", "--max-time", "120", "-o", path]
        if TOKEN:
            cmd += ["-H", f"Authorization: Bearer {TOKEN}"]
        cmd += ["-H", "Accept: application/vnd.github+json", url]
        subprocess.run(cmd, check=True)
        with open(path, "rb") as f:
            return json.load(f)
    finally:
        os.unlink(path)


def norm_version(tag):
    out = []
    for part in tag.lstrip("vV").split("."):
        num = "".join(c for c in part if c.isdigit())
        if not num:
            break
        out.append(str(int(num)))
    return ".".join(out) if out else tag.lstrip("vV")


def version_key(v):
    return [int(x) if x.isdigit() else 0 for x in v["version"].split(".")]


def parse_apps():
    apps = []
    path = os.path.join(ROOT, "apps.txt")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            cols = line.split()
            if len(cols) < 2 or "/" not in cols[1]:
                print(f"  ! skipping malformed line: {line}", file=sys.stderr)
                continue
            meta = {"name": cols[0], "repo": cols[1]}
            if len(cols) > 2:
                meta["bundle"] = cols[2]
            if len(cols) > 3:
                meta["min_os"] = cols[3]
            if len(cols) > 4:
                meta["tint"] = cols[4]
            apps.append(meta)
    return apps


def load_meta(name):
    path = os.path.join(ROOT, "apps", name, "meta.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def pick_asset(assets, name):
    """Prefer an .ipa asset; ignore source archives and Android/macOS/Windows builds."""
    ipas = [a for a in assets if a["name"].lower().endswith(".ipa")]
    if not ipas:
        return None
    # prefer one whose filename mentions the app, else the smallest (usually arm64-only)
    named = [a for a in ipas if name.lower().replace(" ", "") in a["name"].lower().replace("-", "")]
    cands = named or ipas
    # skip "unsigned" only as a tie-breaker, not a filter
    cands.sort(key=lambda a: (("unsigned" in a["name"].lower()), a["size"]))
    return cands[0]


def build_app(meta):
    name, repo = meta["name"], meta["repo"]
    extra = load_meta(name)
    print(f"==> {name} ({repo})")
    releases = api_json(f"https://api.github.com/repos/{repo}/releases?per_page=100")

    seen, versions = set(), []
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        asset = pick_asset(rel.get("assets", []), name)
        if not asset:
            continue
        ver = norm_version(rel["tag_name"])
        if ver in seen:
            continue
        seen.add(ver)
        versions.append({
            "version": ver,
            "buildVersion": ver,
            "date": rel["published_at"].replace("Z", "+00:00"),
            "downloadURL": f"https://github.com/{repo}/releases/download/"
                           f"{rel['tag_name']}/{asset['name']}",
            "size": asset["size"],
            "minOSVersion": extra.get("min_os", "15.0"),
        })
        if len(versions) >= MAX_VERSIONS:
            break

    versions.sort(key=version_key)
    if not versions:
        print(f"  ! no IPA assets found, skipping")
        return None

    print(f"  {len(versions)} version(s): {[v['version'] for v in versions]}")
    icon_url = raw_url(f"apps/{name}/icon.png")
    desc = extra.get("description", f"Source for {name}.")
    desc_html = "".join(f"<p>{p}</p>" for p in desc.split("\n") if p.strip())

    app = {
        "name": name,
        "bundleIdentifier": extra.get("bundle") or f"com.example.{name.lower()}",
        "developerName": extra.get("developer") or repo.split("/")[0],
        "subtitle": extra.get("subtitle", ""),
        "localizedDescription": desc_html,
        "iconURL": icon_url,
        "tintColor": extra.get("tint", "#3B82F6"),
        "category": extra.get("category", "utilities"),
        "screenshots": extra.get("screenshots", []),
        "versions": versions,
        "appPermissions": {"entitlements": [], "privacy": {}},
    }

    out_dir = os.path.join(ROOT, "apps", name)
    os.makedirs(out_dir, exist_ok=True)

    flat = {
        "name": name,
        "subtitle": extra.get("source_subtitle", extra.get("subtitle", "")),
        "description": desc,
        "iconURL": icon_url,
        "website": f"https://github.com/{repo}",
        "tintColor": extra.get("tint", "#3B82F6"),
        "apps": [app],
    }
    write_json(os.path.join(out_dir, "apps.json"), flat)
    write_json(os.path.join(out_dir, "apps-proxy.json"), deep_proxify(flat))

    # keep icon.png alongside the source if the repo doesn't have one yet
    ensure_icon(out_dir, name, repo, versions[-1]["downloadURL"])
    return app


def ensure_icon(out_dir, name, repo, download_url):
    """Extract the app icon from the newest IPA if apps/<Name>/icon.png is missing."""
    icon_path = os.path.join(out_dir, "icon.png")
    if os.path.exists(icon_path):
        return
    try:
        from PIL import Image
    except ImportError:
        print("  ! Pillow missing, cannot extract icon")
        return
    print("  extracting icon from IPA …")
    fd, ipa_path = tempfile.mkstemp(suffix=".ipa")
    os.close(fd)
    try:
        subprocess.run(["curl", "-sfL", "--max-time", "300", "-o", ipa_path, download_url],
                       check=True)
        with zipfile.ZipFile(ipa_path) as z:
            cands = [n for n in z.namelist() if "AppIcon" in n and n.endswith(".png")]
            if not cands:
                print("  ! no AppIcon png in bundle (icons may be in Assets.car)")
                return
            cands.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)
            data = z.read(cands[0])
        data = cgbi_to_png(data) if data[12:16] == b"CgBI" else data
        im = Image.open(io.BytesIO(data))
        im.load()
        im.convert("RGB").resize((512, 512), Image.LANCZOS).save(icon_path, optimize=True)
        print(f"  icon written ({len(data)}B source → {os.path.getsize(icon_path)}B)")
    except Exception as e:  # noqa: BLE001 - icon is nice-to-have, never fail the build
        print(f"  ! icon extraction failed: {e}")
    finally:
        os.unlink(ipa_path)


def cgbi_to_png(data):
    """Convert Apple-optimised (CgBI) PNG to a standard PNG readable by Pillow."""
    import struct
    import zlib

    pos, idat, ihdr, plte = 8, b"", None, b""
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"CgBI":
            continue
        if typ == b"IHDR":
            ihdr = body
        elif typ == b"PLTE":
            plte = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    w, h, _depth, ctype = struct.unpack(">IIBB", ihdr[:10])
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        raw = zlib.decompressobj(-15).decompress(idat)
    bpp = {6: 4, 2: 3, 0: 1, 4: 2}[ctype]
    stride = w * bpp
    out = bytearray()
    for y in range(h):
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if bpp >= 3:
            for x in range(0, len(line), bpp):
                line[x], line[x + 2] = line[x + 2], line[x]
        out.append(0)
        out += line

    def chunk(t, b):
        return (struct.pack(">I", len(b)) + t + b
                + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + (chunk(b"PLTE", plte) if plte else b"")
            + chunk(b"IDAT", zlib.compress(bytes(out), 9)) + chunk(b"IEND", b""))


def deep_proxify(obj):
    if isinstance(obj, dict):
        return {k: deep_proxify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_proxify(v) for v in obj]
    if isinstance(obj, str):
        return proxify(obj)
    return obj


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    global OWNER_REPO
    if not OWNER_REPO:
        OWNER_REPO = os.environ.get("GITHUB_REPOSITORY", "")

    # allow running locally: detect origin remote
    if not OWNER_REPO and os.path.isdir(os.path.join(ROOT, ".git")):
        try:
            url = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"],
                                 capture_output=True, text=True, check=True).stdout.strip()
            m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
            if m:
                OWNER_REPO = m.group(1)
        except subprocess.CalledProcessError:
            pass

    if not OWNER_REPO:
        sys.exit("SOURCE_REPO or GITHUB_REPOSITORY must be set")

    apps = parse_apps()
    if not apps:
        sys.exit("no apps in apps.txt")

    built = []
    for meta in apps:
        try:
            app = build_app(meta)
            if app:
                built.append(app)
        except Exception as e:  # noqa: BLE001 - one bad repo shouldn't kill the run
            print(f"  ! {meta['name']} failed: {e}", file=sys.stderr)

    combined = {
        "name": "LC-source",
        "subtitle": "我自己的 AltStore 软件源",
        "description": "个人自用的 AltStore / LiveContainer 源，收录 GitHub 上的开源 IPA 项目。",
        "iconURL": raw_url("assets/icon.png"),
        "website": f"https://github.com/{OWNER_REPO}",
        "tintColor": "#3B82F6",
        "apps": built,
    }
    write_json(os.path.join(ROOT, "all-apps.json"), combined)
    write_json(os.path.join(ROOT, "all-apps-proxy.json"), deep_proxify(combined))
    print(f"\n✔ wrote {len(built)} app(s) to all-apps.json")


if __name__ == "__main__":
    main()
