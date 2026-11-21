import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    timeout: float = 45
    retries: int = 1
    db_path: str = "data/sessions.sqlite3"
    context_budget: int = 6000
    max_steps: int = 6
    corpus_dir: str = "corpus"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    local_files_only: bool = True
    retrieval_mode: str = "bm25"
    use_rerank: bool = False

    def __post_init__(self):
        if not 0 < self.timeout <= 300 or not 0 <= self.retries <= 2:
            raise ValueError("Invalid timeout/retries")
        if not 1 <= self.max_steps <= 6 or self.context_budget < 100:
            raise ValueError("Invalid steps/context budget")
        if self.retrieval_mode not in ("bm25", "dense", "hybrid"):
            raise ValueError("Invalid retrieval mode")
        for name in ("db_path", "corpus_dir"):
            p = Path(getattr(self, name))
            if not p.is_absolute():
                setattr(self, name, str(ROOT / p))


def load_settings():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        llm_model=os.getenv("LLM_MODEL", "deepseek-flash"),
        timeout=float(os.getenv("LLM_TIMEOUT", "45")),
        retries=int(os.getenv("LLM_RETRIES", "1")),
        db_path=os.getenv("DB_PATH", "data/sessions.sqlite3"),
        context_budget=int(os.getenv("CONTEXT_BUDGET", "6000")),
        max_steps=int(os.getenv("MAX_STEPS", "6")),
        corpus_dir=os.getenv("CORPUS_DIR", "corpus"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        reranker_model=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
        local_files_only=os.getenv("LOCAL_FILES_ONLY", "true").lower() == "true",
        retrieval_mode=os.getenv("RETRIEVAL_MODE", "bm25"),
        use_rerank=os.getenv("RERANK", "false").lower() == "true",
    )
