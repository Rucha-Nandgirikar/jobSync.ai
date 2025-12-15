from pathlib import Path
from typing import List, Any

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    CSVLoader,
    Docx2txtLoader,
    JSONLoader,
)
from langchain_community.document_loaders.excel import UnstructuredExcelLoader


def load_all_documents(data_dir: str) -> List[Any]:
    """Load all supported files from a directory into LangChain Documents.

    Supported: PDF, TXT, CSV, Excel (.xlsx), Word (.docx), JSON.
    """
    data_path = Path(data_dir).resolve()
    print(f"[RAG] Data path: {data_path}")

    documents: List[Any] = []

    # PDF
    for pdf_file in data_path.glob("**/*.pdf"):
        try:
            loader = PyPDFLoader(str(pdf_file))
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:  # pragma: no cover - debug logging only
            print(f"[RAG][ERROR] Failed to load PDF {pdf_file}: {e}")

    # TXT
    for txt_file in data_path.glob("**/*.txt"):
        try:
            loader = TextLoader(str(txt_file))
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"[RAG][ERROR] Failed to load TXT {txt_file}: {e}")

    # CSV
    for csv_file in data_path.glob("**/*.csv"):
        try:
            loader = CSVLoader(str(csv_file))
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"[RAG][ERROR] Failed to load CSV {csv_file}: {e}")

    # Excel
    for xlsx_file in data_path.glob("**/*.xlsx"):
        try:
            loader = UnstructuredExcelLoader(str(xlsx_file))
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"[RAG][ERROR] Failed to load Excel {xlsx_file}: {e}")

    # Word
    for docx_file in data_path.glob("**/*.docx"):
        try:
            loader = Docx2txtLoader(str(docx_file))
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"[RAG][ERROR] Failed to load Word {docx_file}: {e}")

    # JSON
    for json_file in data_path.glob("**/*.json"):
        try:
            loader = JSONLoader(str(json_file))
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"[RAG][ERROR] Failed to load JSON {json_file}: {e}")

    print(f"[RAG] Total loaded documents: {len(documents)}")
    return documents




