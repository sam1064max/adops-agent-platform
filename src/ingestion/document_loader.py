"""Document loading and chunking for the RAG ingestion pipeline."""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represents a loaded document with content and metadata."""

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A chunk of a document with metadata."""

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def _parse_frontmatter(content: str) -> tuple[Dict[str, str], str]:
    """Parse YAML-style frontmatter from document content.

    Returns:
        Tuple of (metadata_dict, remaining_content).
    """
    frontmatter_pattern = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL
    )
    match = frontmatter_pattern.match(content)
    if not match:
        return {}, content

    raw_fm = match.group(1)
    metadata = {}
    for line in raw_fm.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.lower() == "true":
                value = "true"
            elif value.lower() == "false":
                value = "false"
            metadata[key] = value

    remaining = content[match.end():]
    return metadata, remaining


def _extract_sections(content: str) -> List[Dict[str, str]]:
    """Extract markdown sections (headers) from content.

    Returns:
        List of dicts with 'header' and 'text' keys.
    """
    sections = []
    current_header = ""
    current_lines: List[str] = []

    for line in content.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            if current_lines:
                sections.append({
                    "header": current_header,
                    "text": "\n".join(current_lines).strip(),
                })
            current_header = re.sub(r"^#{1,6}\s+", "", line).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({
            "header": current_header,
            "text": "\n".join(current_lines).strip(),
        })

    return sections


def _split_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[str]:
    """Split text into chunks of approximately chunk_size characters.

    Tries to split on sentence boundaries when possible.
    """
    if len(text) <= chunk_size:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_length + sentence_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))

            # Calculate overlap: reuse sentences from end of previous chunk
            overlap_sentences: List[str] = []
            overlap_len = 0
            for s in reversed(current_chunk):
                if overlap_len + len(s) > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += len(s)

            current_chunk = overlap_sentences
            current_length = overlap_len

        current_chunk.append(sentence)
        current_length += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


class DocumentLoader:
    """Loads and processes markdown documents from the knowledge base."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_knowledge_base(
        self, path: str = "knowledge_base/"
    ) -> List[Document]:
        """Load all .md files from the knowledge base directory.

        Args:
            path: Path to the knowledge base directory.

        Returns:
            List of Document objects with parsed content and metadata.

        Raises:
            FileNotFoundError: If the directory does not exist.
        """
        kb_path = Path(path)
        if not kb_path.exists():
            raise FileNotFoundError(
                f"Knowledge base directory not found: {path}"
            )
        if not kb_path.is_dir():
            raise NotADirectoryError(
                f"Path is not a directory: {path}"
            )

        documents: List[Document] = []
        md_files = sorted(kb_path.glob("**/*.md"))

        if not md_files:
            logger.warning("No .md files found in %s", path)
            return documents

        for md_file in md_files:
            try:
                doc = self._load_single_file(md_file, kb_path)
                if doc:
                    documents.append(doc)
            except Exception:
                logger.exception(
                    "Failed to load file: %s", md_file
                )

        logger.info(
            "Loaded %d documents from %s", len(documents), path
        )
        return documents

    def _load_single_file(
        self, file_path: Path, base_path: Path
    ) -> Optional[Document]:
        """Load a single markdown file.

        Args:
            file_path: Absolute path to the markdown file.
            base_path: Base knowledge base path for relative filenames.

        Returns:
            Document object or None if empty.
        """
        content = file_path.read_text(encoding="utf-8")
        if not content.strip():
            logger.debug("Skipping empty file: %s", file_path)
            return None

        frontmatter, body = _parse_frontmatter(content)
        sections = _extract_sections(body)

        relative_path = file_path.relative_to(base_path)
        filename = str(relative_path).replace("\\", "/")

        metadata = {
            "filename": filename,
            "sections": sections,
            **frontmatter,
        }

        return Document(content=body.strip(), metadata=metadata)

    def chunk_documents(
        self, documents: List[Document]
    ) -> List[Chunk]:
        """Split documents into chunks with metadata.

        Args:
            documents: List of Document objects to chunk.

        Returns:
            List of Chunk objects.
        """
        all_chunks: List[Chunk] = []

        for doc in documents:
            doc_chunks = self._chunk_single_document(doc)
            all_chunks.extend(doc_chunks)

        logger.info(
            "Created %d chunks from %d documents",
            len(all_chunks),
            len(documents),
        )
        return all_chunks

    def _chunk_single_document(self, doc: Document) -> List[Chunk]:
        """Chunk a single document.

        Args:
            doc: Document to chunk.

        Returns:
            List of Chunk objects.
        """
        content = doc.content
        filename = doc.metadata.get("filename", "unknown")
        sections = doc.metadata.get("sections", [])

        if not sections:
            # No sections found, chunk the whole content
            return self._make_chunks(
                content, filename, section_header=""
            )

        chunks: List[Chunk] = []
        for section in sections:
            header = section.get("header", "")
            text = section.get("text", "")
            if not text.strip():
                continue
            section_chunks = self._make_chunks(
                text, filename, section_header=header
            )
            chunks.extend(section_chunks)

        return chunks

    def _make_chunks(
        self,
        text: str,
        source_file: str,
        section_header: str = "",
    ) -> List[Chunk]:
        """Create chunks from text with metadata.

        Args:
            text: Text to chunk.
            source_file: Source filename.
            section_header: Section header text.

        Returns:
            List of Chunk objects.
        """
        raw_chunks = _split_text(
            text, self.chunk_size, self.chunk_overlap
        )
        chunks = []

        for idx, chunk_text in enumerate(raw_chunks):
            if not chunk_text.strip():
                continue
            metadata = {
                "source_file": source_file,
                "chunk_index": idx,
                "section_header": section_header,
            }
            chunks.append(Chunk(content=chunk_text, metadata=metadata))

        return chunks
