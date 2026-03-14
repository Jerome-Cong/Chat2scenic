import re
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import (
    UnstructuredPDFLoader,
)
from langchain_core.documents import Document


def load_pdf(path: Path) -> Optional[Document]:
    loader = UnstructuredPDFLoader(str(path))
    docs = loader.load()
    if not docs:
        return None
    cleaned_txt = clean(docs[0].page_content)
    return Document(page_content=cleaned_txt)


def clean(text: str) -> str:
    """
    Clean up text extracted from PDFs:
    - remove page numbers like "Page 3", "3 / 97" on their own line
    - remove long dotted lines (e.g., "..........." in table of contents)
    - collapse multiple spaces/tabs into a single space
    - collapse multiple blank lines into a single newline
    - strip leading and trailing whitespace from each line and the whole text
    """
    # remove the page numbers
    text = re.sub(
    r'^\s*(Page\s+\d+|\d+\s*/\s*\d+)\s*$',
    '',
    text,
    flags=re.MULTILINE | re.IGNORECASE
    )

    # Remove sequences of three or more dots
    text = re.sub(r'\.{3,}', '', text)

    # Replace multiple spaces or tabs with a single space
    text = re.sub(r'[ \t]+', ' ', text)

    # Replace multiple consecutive newlines with a single newline
    text = re.sub(r'\n{2,}', '\n', text)

    # Strip leading and trailing whitespace from each line  
    text = "\n".join(line.strip() for line in text.splitlines())

    # Strip leading and trailing whitespace from the entire text
    text = text.strip()

    return text
