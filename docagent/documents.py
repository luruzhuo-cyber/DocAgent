"""Parse uploads before publishing their searchable Markdown."""

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

FORMATS = {".md", ".txt", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
LIMIT = 20 * 1024 * 1024


def parse_document(name, data):
    suffix = Path(name).suffix.lower()
    if suffix not in FORMATS:
        raise ValueError("不支持的文件格式")
    if suffix in {".md", ".txt"}:
        text = data.decode("utf-8-sig")
    elif suffix == ".pdf":
        import pymupdf as fitz

        with fitz.open(stream=data, filetype="pdf") as pdf:
            text = "\n\n".join(
                f"## 第 {i} 页\n\n{page.get_text()}"
                for i, page in enumerate(pdf, 1)
                if page.get_text().strip()
            )
    elif suffix == ".docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = Document(io.BytesIO(data))
        blocks = []
        for item in doc.element.body:
            if item.tag.endswith("}p"):
                p = Paragraph(item, doc)
                heading = p.style.name.startswith("Heading")
                blocks.append(("## " if heading else "") + p.text)
            elif item.tag.endswith("}tbl"):
                blocks.extend(
                    " | ".join(cell.text for cell in row.cells)
                    for row in Table(item, doc).rows
                )
        text = "\n\n".join(blocks)
    else:
        binary = shutil.which("tesseract")
        if not binary:
            raise ValueError("图片 OCR 需要安装 Tesseract 并加入 PATH")
        import os

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ("image" + suffix)
            path.write_bytes(data)
            result = subprocess.run(
                [
                    binary,
                    str(path),
                    "stdout",
                    "-l",
                    os.getenv("OCR_LANG", "chi_sim+eng"),
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            if result.returncode:
                raise ValueError("图片识别失败，请检查 OCR 语言包和图片格式")
            text = result.stdout.decode("utf-8")
    if not text.strip():
        raise ValueError("没有可检索文字。扫描 PDF 可先转为图片后导入")
    return text.strip()
