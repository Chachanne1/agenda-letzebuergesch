"""Enregistre localement des pages d'agenda pour que je puisse écrire les scrapers.

Usage :   python scrapers/snapshot.py
Résultat : un dossier snapshots/ et un fichier snapshots.zip à m'envoyer.

Pour chaque URL de urls.txt : la page de liste, 2 pages de détail d'événement
(détectées automatiquement) et, si le site est WordPress, la liste de ses types
de contenu avec 3 exemples de chaque type d'événement. Pages publiques uniquement.
"""
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "snapshots"
UA = "agenda-letzebuergesch/0.1 (+https://github.com/Chachanne1/agenda-letzebuergesch)"
MAX_BYTES = 1_500_000
SKIP_TYPES = {"post", "page", "attachment", "nav_menu_item", "wp_block", "wp_template",
              "wp_template_part", "wp_navigation", "wp_global_styles", "wp_font_family",
              "wp_font_face", "revision", "menu_item"}
DETAIL_HINTS = ("event", "evenement", "agenda", "programm", "veranstaltung", "spectacle", "concert", "/fr/", "/en/")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(MAX_BYTES).decode("utf-8", errors="replace")


def slug(url, suffix=""):
    p = urllib.parse.urlparse(url)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (p.netloc + p.path).strip("/"))[:60]
    return f"{s}{suffix}"


def save(name, text, index):
    (OUT / name).write_text(text, encoding="utf-8")
    index.append(name)


def read_urls():
    urls = []
    for line in (ROOT / "urls.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line.startswith("http") and "wp-json" not in line:
            urls.append(line)
    return urls


def detail_links(html, base):
    host = urllib.parse.urlparse(base).netloc
    seen, out = set(), []
    for href in re.findall(r'href="([^"#]+)"', html):
        full = urllib.parse.urljoin(base, href)
        pu = urllib.parse.urlparse(full)
        if pu.netloc != host or full.rstrip("/") == base.rstrip("/") or full in seen:
            continue
        depth = len([x for x in pu.path.split("/") if x])
        if depth >= 3 and any(h in full.lower() for h in DETAIL_HINTS) and not re.search(r"\.(jpg|png|pdf|css|js|svg)$", full):
            seen.add(full)
            out.append(full)
    return out[:2]


def wordpress(html, base, prefix, index, log):
    m = re.search(r'<link[^>]+rel=["\']https://api\.w\.org/["\'][^>]+href=["\']([^"\']+)["\']', html)
    if not m:
        return
    root = m.group(1)
    try:
        types = json.loads(get(root.rstrip("/") + "/wp/v2/types"))
    except Exception as exc:
        log.append(f"   wp types: {exc}")
        return
    save(f"{prefix}_wp_types.json", json.dumps({k: v.get("rest_base") for k, v in types.items()}, indent=1), index)
    for key, info in types.items():
        if key in SKIP_TYPES or not info.get("rest_base"):
            continue
        try:
            sample = get(f"{root.rstrip('/')}/wp/v2/{info['rest_base']}?per_page=3")
            save(f"{prefix}_wp_{key}.json", sample, index)
            log.append(f"   wp type {key}: ok")
        except Exception as exc:
            log.append(f"   wp type {key}: {exc}")
        time.sleep(1)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    index, log = [], []
    for i, url in enumerate(read_urls(), 1):
        prefix = f"{i:02d}_{slug(url)}"
        log.append(f"[{i}] {url}")
        try:
            html = get(url)
        except Exception as exc:
            log.append(f"   ERREUR {type(exc).__name__}: {exc}")
            print(log[-2], log[-1])
            continue
        save(f"{prefix}.html", html, index)
        for j, link in enumerate(detail_links(html, url), 1):
            time.sleep(1)
            try:
                save(f"{prefix}_detail{j}.html", f"<!-- {link} -->\n" + get(link), index)
                log.append(f"   détail {j}: {link}")
            except Exception as exc:
                log.append(f"   détail {j} ERREUR: {exc}")
        wordpress(html, url, prefix, index, log)
        print("\n".join(l for l in log if l.startswith("[") or l.startswith("   ")) and log[-1])
        time.sleep(1)
    # pages de détail précises (urls_detail.txt), enregistrées telles quelles
    detail_file = ROOT / "urls_detail.txt"
    if detail_file.exists():
        n = 0
        for line in detail_file.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line.startswith("http"):
                continue
            n += 1
            name = f"detail_{n:02d}_{slug(line)}.html"
            try:
                save(name, f"<!-- {line} -->\n" + get(line), index)
                log.append(f"[détail {n}] {line} : ok")
            except Exception as exc:
                log.append(f"[détail {n}] {line} : ERREUR {exc}")
            print(log[-1])
            time.sleep(1)
    (OUT / "_journal.txt").write_text("\n".join(log), encoding="utf-8")
    shutil.make_archive(str(ROOT / "snapshots"), "zip", OUT)
    size = (ROOT / "snapshots.zip").stat().st_size // 1024
    print(f"\nTerminé : {len(index)} fichiers, snapshots.zip ({size} Ko). Envoyez ce fichier dans le chat.")


if __name__ == "__main__":
    sys.exit(main())
