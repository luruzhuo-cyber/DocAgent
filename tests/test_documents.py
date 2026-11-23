import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf as fitz
from docx import Document
from fastapi.testclient import TestClient
from docagent import api
from docagent.config import Settings
from docagent.documents import parse_document


class DocumentTests(unittest.TestCase):
    def test_docx_table_and_pdf_page(self):
        doc = Document()
        doc.add_heading("Project", level=1)
        doc.add_table(rows=1, cols=1).cell(0, 0).text = "Table value"
        buffer = io.BytesIO()
        doc.save(buffer)
        self.assertIn("Table value", parse_document("sample.docx", buffer.getvalue()))
        with fitz.open() as pdf:
            pdf.new_page().insert_text((30, 30), "PDF evidence")
            result = parse_document("sample.pdf", pdf.tobytes())
        self.assertIn("PDF evidence", result)
        self.assertIn("第 1 页", result)

    def test_upload_list_search_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = Settings(corpus_dir=str(root), db_path=str(root / "test.db"))
            with patch.object(
                api, "load_settings", return_value=settings
            ), patch.object(api, "_engine", None):
                with TestClient(api.app) as client:
                    upload = client.put(
                        "/documents/upload",
                        params={"filename": "sample.txt"},
                        content=b"UniqueSeal42",
                    )
                    self.assertEqual(upload.status_code, 200)
                    key = upload.json()["id"]
                    self.assertEqual(
                        client.get("/documents").json()["documents"][0]["name"],
                        "sample.txt",
                    )
                    self.assertTrue(
                        api.get_engine().retriever.search("UniqueSeal42")["hits"]
                    )
                    self.assertEqual(
                        client.delete("/documents/" + key).status_code, 200
                    )
                    self.assertFalse(
                        api.get_engine().retriever.search("UniqueSeal42")["hits"]
                    )
                    self.assertEqual(client.get("/documents").json()["documents"], [])
