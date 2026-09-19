"""YouTube download via yt-dlp, routed through public proxy pools.

The VM's datacenter IP is bot-blocked by YouTube, so downloads must go
through a working public HTTP proxy. We fetch a fresh proxy list,
parallel-test them against youtube.com, and keep only working ones.
"""
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROXY_LIST_URL = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
PROXY_CACHE = Path(__file__).parent.parent / "proxies.txt"
WORKING_CACHE = Path(__file__).parent.parent / "proxies_working.txt"


def _fetch_proxy_list(limit: int = 100) -> list:
    PROXY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "-s", "-m", "20", PROXY_LIST_URL, "-o", str(PROXY_CACHE)],
        check=False,
    )
    try:
        text = PROXY_CACHE.read_text()
    except OSError:
        return []
    proxies = [l.strip() for l in text.splitlines() if l.strip()]
    return proxies[:limit]


def test_proxy(proxy: str, timeout: int = 8) -> bool:
    """Check if a proxy can reach YouTube."""
    try:
        res = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-m", str(timeout),
             "-w", "%{http_code}", "-x", f"http://{proxy}",
             "https://www.youtube.com"],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        return res.stdout.strip() == "200"
    except Exception:
        return False


def find_working_proxies(max_proxies: int = 5) -> list:
    """Parallel-test proxies, return up to max_proxies working ones."""
    proxies = _fetch_proxy_list()
    if not proxies:
        return []
    working = []
    with ThreadPoolExecutor(max_workers=30) as pool:
        for proxy, ok in zip(proxies, pool.map(test_proxy, proxies)):
            if ok:
                working.append(proxy)
                if len(working) >= max_proxies:
                    break
    if working:
        WORKING_CACHE.write_text("\n".join(working))
    return working


def download_via_proxy(url_or_search: str, out_dir: Path, proxies: list,
                       duration_filter: str = "duration<600",
                       extra: list = None) -> list:
    """Download via a list of proxies (fallback on failure). Return paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    for proxy in proxies:
        cmd = [
            "yt-dlp",
            "--proxy", f"http://{proxy}",
            "--match-filter", duration_filter + " & title!~=watermark & title!~=envato & title!~=intro",
            "--max-downloads", "1",
            "--print", "after_move:filepath",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--format", "mp4",
            "-o", str(out_dir / "%(id)s.%(ext)s"),
        ] + (extra or []) + [url_or_search]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=600)
            files = [f for f in res.stdout.strip().splitlines() if f.strip()]
            if files:
                return files
            errors.append(res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "empty")
        except subprocess.TimeoutExpired:
            errors.append(f"{proxy}: timeout")
    raise RuntimeError(f"All proxies failed: {'; '.join(errors[:3])}")
