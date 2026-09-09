"""
Loads transcripts from the Lenny's Podcast Transcripts GitHub repo.

Repo structure (confirmed against the live repo):
    episodes/{guest-slug}/transcript.md
        --- (YAML frontmatter: guest, title, youtube_url, video_id,
             publish_date, description, duration_seconds, duration,
             view_count, channel, keywords) ---
        # Markdown transcript body

We shallow-clone the repo (depth=1) into a working directory rather than
using the GitHub API, since it's simpler and avoids API rate limits for
300+ files. Re-running ingestion re-clones fresh, so "refresh" is just
"run ingestion again" (content_hash on each document skips unchanged ones
at the DB layer — see ingest.py).
"""

import hashlib
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config import get_settings

logger = logging.getLogger("lenny.rag.loader")

CLONE_DIR = Path("/tmp/transcript-source")


@dataclass
class LoadedTranscript:
    source_path: str        # relative path, used as the stable document key
    title: str | None
    guest: str | None
    publish_date: str | None
    content_hash: str
    body: str                # markdown transcript text (frontmatter stripped)


def _clone_repo() -> Path:
    settings = get_settings()
    if CLONE_DIR.exists():
        shutil.rmtree(CLONE_DIR)

    logger.info("Cloning transcript repo: %s", settings.transcript_repo_url)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", settings.transcript_repo_url, str(CLONE_DIR)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr}")

    return CLONE_DIR


def _parse_transcript_file(path: Path, repo_root: Path) -> LoadedTranscript | None:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        logger.warning("Skipping malformed transcript (no frontmatter): %s", path)
        return None

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        logger.warning("Skipping transcript with invalid YAML frontmatter %s: %s", path, exc)
        return None

    body = parts[2].strip()
    if not body:
        logger.warning("Skipping transcript with empty body: %s", path)
        return None

    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    source_path = str(path.relative_to(repo_root))

    return LoadedTranscript(
        source_path=source_path,
        title=frontmatter.get("title"),
        guest=frontmatter.get("guest"),
        publish_date=frontmatter.get("publish_date"),
        content_hash=content_hash,
        body=body,
    )


def load_all_transcripts(limit: int | None = None) -> list[LoadedTranscript]:
    """
    Clones the repo and parses every episodes/*/transcript.md file.
    `limit` is useful for a fast first-run smoke test before ingesting
    the full ~300-episode corpus.
    """
    repo_root = _clone_repo()
    episodes_dir = repo_root / "episodes"
    if not episodes_dir.exists():
        raise RuntimeError(f"'episodes' folder not found in cloned repo at {repo_root}")

    transcript_files = sorted(episodes_dir.glob("*/transcript.md"))
    if limit:
        transcript_files = transcript_files[:limit]

    logger.info("Found %d transcript files to parse", len(transcript_files))

    loaded: list[LoadedTranscript] = []
    for path in transcript_files:
        parsed = _parse_transcript_file(path, repo_root)
        if parsed:
            loaded.append(parsed)

    logger.info("Successfully parsed %d/%d transcripts", len(loaded), len(transcript_files))
    return loaded