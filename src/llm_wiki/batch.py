from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import DEFAULT_VAULT_DIRNAME, resolve_source_root
from .ingest import IngestResult, ingest_source
from .source_loader import detect_source_file_type, import_local_source


@dataclass(slots=True)
class BatchImportItem:
    original_path: Path
    imported_path: Path | None = None
    ingest_result: IngestResult | None = None
    skipped_reason: str | None = None


@dataclass(slots=True)
class BatchIngestResult:
    directory: Path
    items: list[BatchImportItem] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return sum(1 for item in self.items if item.imported_path is not None)

    @property
    def ingested_count(self) -> int:
        return sum(1 for item in self.items if item.ingest_result is not None)

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.items if item.skipped_reason is not None)


def ingest_directory(
    *,
    base_path: Path,
    directory: Path,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    recurse: bool = True,
    use_llm: bool = True,
    provider_name: str | None = None,
    model: str | None = None,
    max_file_changes: int | None = None,
) -> BatchIngestResult:
    input_dir = directory.resolve()
    if not input_dir.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not input_dir.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    source_root = resolve_source_root(base_path, vault_name)
    items: list[BatchImportItem] = []
    pattern = "**/*" if recurse else "*"
    for path in sorted(input_dir.glob(pattern)):
        if not path.is_file():
            continue
        if detect_source_file_type(path) is None:
            items.append(BatchImportItem(original_path=path, skipped_reason="unsupported source type"))
            continue

        imported_path = import_local_source(path, source_root=source_root, source_base=input_dir)
        ingest_result = ingest_source(
            base_path=base_path,
            source_arg=imported_path.relative_to(source_root).as_posix(),
            vault_name=vault_name,
            use_llm=use_llm,
            provider_name=provider_name,
            model=model,
            max_file_changes=max_file_changes,
        )
        items.append(
            BatchImportItem(
                original_path=path,
                imported_path=imported_path,
                ingest_result=ingest_result,
            )
        )

    return BatchIngestResult(directory=input_dir, items=items)
