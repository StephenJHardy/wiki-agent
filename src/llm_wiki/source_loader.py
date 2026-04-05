from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

import pymupdf
import pymupdf4llm
from trafilatura import extract, html2txt

from .config import DEFAULT_VAULT_DIRNAME, resolve_extracted_root, resolve_source_root, resolve_vault_root
from .filesystem import compute_checksum, ensure_directory, slugify, write_bytes, write_text
from .models import SourceFileType

SUPPORTED_SOURCE_SUFFIXES = {
    ".htm": "html",
    ".html": "html",
    ".markdown": "markdown",
    ".md": "markdown",
    ".pdf": "pdf",
    ".txt": "text",
}
TEXTUAL_SOURCE_TYPES = {"markdown", "text"}


@dataclass(slots=True)
class PreparedSource:
    source_id: str
    source_path: Path
    relative_source_path: str
    file_type: SourceFileType
    source_text: str
    checksum: str
    extracted_path: str | None = None
    original_url: str | None = None


def prepare_source(base_path: Path, source_arg: str, vault_name: str = DEFAULT_VAULT_DIRNAME) -> PreparedSource:
    vault_root = resolve_vault_root(base_path, vault_name)
    source_root = resolve_source_root(base_path, vault_name)
    extracted_root = resolve_extracted_root(base_path, vault_name)
    original_url: str | None = None

    if is_url(source_arg):
        source_path, original_url = snapshot_remote_source(source_arg, source_root)
    else:
        source_path = resolve_source_path(base_path, source_arg, vault_name)

    if not source_path.exists():
        raise FileNotFoundError(f"Source not found: {source_arg}")
    if source_root not in source_path.parents:
        raise ValueError("Sources must live under `vault/raw/sources/`.")

    file_type = detect_source_file_type(source_path)
    if file_type is None:
        raise ValueError("Supported source types are markdown, text, HTML, and PDF.")

    source_id = build_source_id(source_path, file_type)
    relative_source_path = source_path.relative_to(vault_root).as_posix()
    checksum = compute_checksum(source_path)

    if file_type in TEXTUAL_SOURCE_TYPES:
        source_text = read_text_relaxed(source_path)
        extracted_path = None
    elif file_type == "html":
        source_text = extract_html_source(source_path, original_url=original_url)
        extracted_path = write_derived_source(
            extracted_root=extracted_root,
            source_id=source_id,
            file_type=file_type,
            content=source_text,
        )
    else:
        source_text = extract_pdf_source(source_path)
        extracted_path = write_derived_source(
            extracted_root=extracted_root,
            source_id=source_id,
            file_type=file_type,
            content=source_text,
        )

    return PreparedSource(
        source_id=source_id,
        source_path=source_path,
        relative_source_path=relative_source_path,
        file_type=file_type,
        source_text=source_text,
        checksum=checksum,
        extracted_path=extracted_path,
        original_url=original_url,
    )


def resolve_source_path(base_path: Path, source_arg: str, vault_name: str) -> Path:
    candidate = Path(source_arg)
    if candidate.is_absolute():
        return candidate

    direct = (base_path / candidate).resolve()
    if direct.exists():
        return direct

    return (resolve_source_root(base_path, vault_name) / source_arg).resolve()


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_source_id(path: Path, file_type: SourceFileType) -> str:
    if file_type in TEXTUAL_SOURCE_TYPES:
        return slugify(path.stem)
    return slugify(path.name)


def detect_source_file_type(path: Path) -> SourceFileType | None:
    return SUPPORTED_SOURCE_SUFFIXES.get(path.suffix.lower())


def snapshot_remote_source(url: str, source_root: Path) -> tuple[Path, str]:
    payload, content_type, final_url = download_remote_source(url)
    effective_url = final_url or url
    suffix = choose_snapshot_suffix(effective_url, content_type)
    path = build_snapshot_path(source_root, effective_url, suffix)
    if path.exists():
        if compute_checksum(path) == sha256(payload).hexdigest():
            return path, effective_url
        path = path.with_name(f"{path.stem}-{sha256(payload).hexdigest()[:8]}{path.suffix}")
    write_bytes(path, payload)
    return path, effective_url


def download_remote_source(url: str) -> tuple[bytes, str | None, str]:
    request = Request(url, headers={"User-Agent": "llm-wiki/0.1"})
    with urlopen(request, timeout=30) as response:
        payload = response.read()
        content_type = response.headers.get_content_type()
        final_url = response.geturl()
    return payload, content_type, final_url


def choose_snapshot_suffix(url: str, content_type: str | None) -> str:
    path_suffix = Path(urlparse(url).path).suffix.lower()
    if path_suffix in SUPPORTED_SOURCE_SUFFIXES:
        return path_suffix
    if content_type == "application/pdf":
        return ".pdf"
    if content_type in {"text/plain"}:
        return ".txt"
    return ".html"


def build_snapshot_path(source_root: Path, url: str, suffix: str) -> Path:
    parsed = urlparse(url)
    path_fragment = unquote(parsed.path).strip("/") or "index"
    stem = slugify(f"{parsed.netloc} {path_fragment}")
    url_hash = sha1(url.encode("utf-8")).hexdigest()[:8]
    ensure_directory(source_root)
    return source_root / f"{stem}-{url_hash}{suffix}"


def extract_html_source(path: Path, *, original_url: str | None) -> str:
    html_text = read_text_relaxed(path)
    extracted = extract(
        html_text,
        url=original_url,
        output_format="markdown",
        with_metadata=True,
        include_formatting=True,
        include_links=True,
        include_tables=True,
    )
    if extracted:
        return extracted.strip()
    return html2txt(html_text).strip() or html_text.strip()


def extract_pdf_source(path: Path) -> str:
    try:
        extracted = str(pymupdf4llm.to_markdown(str(path)) or "").strip()
    except Exception:
        extracted = ""
    if extracted:
        return extracted

    document = pymupdf.open(path)
    try:
        pages = [page.get_text("text").strip() for page in document]
    finally:
        document.close()
    return "\n\n".join(page for page in pages if page).strip()


def write_derived_source(
    *,
    extracted_root: Path,
    source_id: str,
    file_type: SourceFileType,
    content: str,
) -> str:
    suffix = ".md" if file_type in {"html", "pdf"} else ".txt"
    target = extracted_root / f"{source_id}{suffix}"
    write_text(target, content)
    return target.relative_to(extracted_root.parent.parent).as_posix()


def read_text_relaxed(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")
