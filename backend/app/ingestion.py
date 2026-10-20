from hashlib import sha256
from io import BytesIO
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader


def pdf_chunks(data: bytes, filename: str) -> list[Document]:
    pages = PdfReader(BytesIO(data)).pages
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    documents: list[Document] = []

    for page_number, page in enumerate(pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        for chunk_number, chunk in enumerate(splitter.split_text(text)):
            chunk_id = sha256(
                f"{filename}:{page_number}:{chunk_number}:{chunk}".encode()
            ).hexdigest()
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": Path(filename).name,
                        "page": page_number,
                        "chunk_id": chunk_id,
                    },
                )
            )

    if not documents:
        raise ValueError("The PDF contains no extractable text.")
    return documents
