import hashlib, math, re, json
from pathlib import Path
from collections import Counter
from .model_versions import PINNED_REVISIONS


def chunk_text(text, document, strategy="structural", size=800):
    if strategy not in ("structural", "fixed"):
        raise ValueError("Unknown chunk strategy")
    heading_matches = list(re.finditer(r"^#{1,6} (.+)$", text, re.MULTILINE))
    spans = []
    if not heading_matches or heading_matches[0].start() > 0:
        spans.append(
            (0, heading_matches[0].start() if heading_matches else len(text), "介绍")
        )
    for index, match in enumerate(heading_matches):
        end = (
            heading_matches[index + 1].start()
            if index + 1 < len(heading_matches)
            else len(text)
        )
        spans.append((match.start(), end, match.group(1).strip()))
    pieces = []
    if strategy == "fixed":
        pieces = [("fixed", text[i : i + size]) for i in range(0, len(text), size)]
    else:
        heading = "介绍"
        lines = []
        for line in text.splitlines():
            if re.match(r"^#{1,6} ", line):
                if lines:
                    pieces.append((heading, "\n".join(lines)))
                heading = line.lstrip("# ").strip()
                lines = [line]
            else:
                lines.append(line)
        if lines:
            pieces.append((heading, "\n".join(lines)))
    chunks = []
    for piece_index, (section, body) in enumerate(pieces):
        parts = []
        buffer = ""
        for paragraph in re.split(r"(?<=。)|(?<=！)|(?<=？)|\n\n", body):
            if len(buffer) + len(paragraph) > size and buffer:
                parts.append(buffer)
                buffer = ""
            while len(paragraph) > size:
                parts.append(paragraph[:size])
                paragraph = paragraph[size:]
            buffer += paragraph
        if buffer:
            parts.append(buffer)
        for i, part in enumerate(parts):
            value = part.strip()
            if value:
                cid = hashlib.sha256(
                    (document + "\0" + section + "\0" + str(i) + "\0" + value).encode()
                ).hexdigest()[:16]
                if strategy == "fixed":
                    cid = hashlib.sha256(
                        (str(piece_index) + "\0" + cid).encode()
                    ).hexdigest()[:16]
                    start, end = piece_index * size, min(
                        (piece_index + 1) * size, len(text)
                    )
                    sections = list(
                        dict.fromkeys(
                            name
                            for left, right, name in spans
                            if left < end and right > start
                        )
                    )
                else:
                    sections = [section]
                chunks.append(
                    dict(
                        id=cid,
                        document=document,
                        section=section,
                        sections=sections,
                        text=value,
                        source=document,
                    )
                )
    return chunks


def tokens(text):
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text.lower())


class Retriever:
    def __init__(self, settings=None, mode=None, strategy="structural"):
        self.settings = settings if not isinstance(settings, list) else None
        self.mode = mode or getattr(settings, "retrieval_mode", "bm25")
        if self.mode not in ("bm25", "dense", "hybrid"):
            raise ValueError("Unknown retrieval mode")
        self.chunks = (
            settings
            if isinstance(settings, list)
            else [
                c
                for p in sorted(
                    [
                        *Path(settings.corpus_dir).glob("*.md"),
                        *(Path(settings.corpus_dir) / "uploads").glob("*.md"),
                    ]
                )
                for c in chunk_text(p.read_text(encoding="utf-8"), p.name, strategy)
            ]
        )
        if self.settings is not None:
            manifest = Path(settings.corpus_dir) / "provenance.json"
            if manifest.exists():
                sources = {
                    f["file"]: f["source"]
                    for f in json.loads(manifest.read_text(encoding="utf-8-sig"))[
                        "files"
                    ]
                }
                for chunk in self.chunks:
                    chunk["source"] = sources.get(chunk["document"], chunk["document"])
        self.docs = [Counter(tokens(c["text"])) for c in self.chunks]
        self.df = Counter(t for d in self.docs for t in d)
        self.lengths = [sum(d.values()) for d in self.docs]
        self.average = sum(self.lengths) / max(1, len(self.docs))
        self.encoder = None
        self.index = None
        self.reranker = None

    def list_documents(self):
        documents = {}
        for chunk in self.chunks:
            name = chunk["document"]
            uploaded = bool(re.fullmatch(r"[a-f0-9]{32}_.+\.md", name))
            entry = documents.setdefault(
                name,
                {
                    "id": name,
                    "name": name[33:-3] if uploaded else name,
                    "uploaded": uploaded,
                    "chunks": 0,
                },
            )
            entry["chunks"] += 1
        return list(documents.values())

    def _bm25(self, query):
        scores = []
        n = len(self.docs)
        for idx, d in enumerate(self.docs):
            score = 0
            for t in set(tokens(query)):
                df = self.df[t]
                tf = d[t]
                score += (
                    math.log(1 + (n - df + 0.5) / (df + 0.5))
                    * tf
                    * 2.5
                    / (
                        tf
                        + 1.5 * (0.25 + 0.75 * self.lengths[idx] / max(1, self.average))
                    )
                )
            scores.append((idx, score))
        return [i for i, s in sorted(scores, key=lambda x: x[1], reverse=True) if s > 0]

    def _dense(self, query):
        import faiss
        from sentence_transformers import SentenceTransformer

        if self.encoder is None:
            self.encoder = SentenceTransformer(
                self.settings.embedding_model,
                revision=PINNED_REVISIONS.get(self.settings.embedding_model),
                local_files_only=self.settings.local_files_only,
            )
            embeddings = self.encoder.encode(
                [c["text"] for c in self.chunks],
                normalize_embeddings=True,
                convert_to_numpy=True,
                batch_size=4,
            ).astype("float32")
            self.index = faiss.IndexFlatIP(embeddings.shape[1])
            self.index.add(embeddings)
        vector = self.encoder.encode(
            [query], normalize_embeddings=True, convert_to_numpy=True
        ).astype("float32")
        return [
            int(i)
            for i in self.index.search(vector, min(20, len(self.chunks)))[1][0]
            if i >= 0
        ]

    def search(self, query, mode=None, top_k=5, rerank=False):
        mode = mode or self.mode
        if mode not in ("bm25", "dense", "hybrid"):
            raise ValueError("Unknown retrieval mode")
        if not self.chunks:
            return {"hits": [], "trace": {"mode": mode, "rerank": False}}
        rankings = []
        if mode in ("bm25", "hybrid"):
            rankings.append(self._bm25(query))
        if mode in ("dense", "hybrid"):
            rankings.append(self._dense(query))
        scores = {}
        for ranking in rankings:
            for rank, idx in enumerate(ranking):
                scores[idx] = scores.get(idx, 0) + 1 / (60 + rank + 1)
        ids = sorted(scores, key=scores.get, reverse=True)[:20]
        if rerank and ids:
            from sentence_transformers import CrossEncoder

            if self.reranker is None:
                self.reranker = CrossEncoder(
                    self.settings.reranker_model,
                    revision=PINNED_REVISIONS.get(self.settings.reranker_model),
                    max_length=512,
                    local_files_only=self.settings.local_files_only,
                )
            values = self.reranker.predict(
                [(query, self.chunks[i]["text"]) for i in ids], batch_size=4
            )
            ids = [i for _, i in sorted(zip(values, ids), reverse=True)]
        return {
            "hits": [dict(self.chunks[i]) for i in ids[: min(20, max(1, top_k))]],
            "trace": {"mode": mode, "rerank": bool(rerank), "candidates": len(ids)},
        }

    def read_section(self, document, section):
        return [
            dict(c)
            for c in self.chunks
            if c["document"] == document
            and section in c.get("sections", [c["section"]])
        ][:10]
