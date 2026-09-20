"""
MemOS (MemoryOS) as a REVOKE memory backend.

Method.  MemOS -- "MemOS: A Memory OS for AI System", Li et al., 2025
(arXiv:2507.03724), MemTensor.  Source: the official repository
https://github.com/MemTensor/MemOS, cloned at commit 176d4f6 ("Dev v2.0.34")
under scratchpad/frameworks/MemOS and installed from PyPI as MemoryOS==2.0.33
(the release that commit tags in pyproject.toml).  Files used:
    src/memos/memories/textual/general.py   GeneralTextMemory: extract / add / search
    src/memos/templates/mem_reader_prompts.py  SIMPLE_STRUCT_MEM_READER_PROMPT
    src/memos/memories/textual/item.py      TextualMemoryItem / TextualMemoryMetadata
    src/memos/vec_dbs/qdrant.py             QdrantVecDB (vector store)
    src/memos/llms/factory.py, embedders/factory.py, vec_dbs/factory.py  registries
    src/memos/mem_os/core.py                MOS.add / MOS.search / _build_system_prompt

What runs here is MemOS's own textual-memory pipeline, imported and wrapped:
the `general_text` memory (GeneralTextMemory) with its Qdrant vector store,
its extraction prompt, its item schema and its retrieval.  The MOS facade
(MOSCore: SQLite user manager, MemCube registry, chat loop, scheduler) is not
instantiated: for a `general_text` cube MOS.add / MOS.search are thin
dispatchers to cube.text_mem.add / .search, and the facade needs a SQLite user
database plus a MemReader whose sentence chunker fetches a tokenizer from the
Hugging Face hub -- neither is wanted in an offline harness.  The tree_text
variant (graph memory with the reorganiser) needs a Neo4j server and is not
used.  Note one consequence: for `general_text` cubes MOS.add stores strings
verbatim and only the tree_text path runs the LLM MemReader; here the sessions
DO go through GeneralTextMemory.extract(), which is the same
SIMPLE_STRUCT_MEM_READER_PROMPT the MemReader uses, so the backend is MemOS's
extraction -> memory items -> embedding retrieval, as the paper describes it.

Mapping onto the contract
    begin_episode(item, persist)  persist=False -> GeneralTextMemory.delete_all()
                                  (MemOS's own reset: drop and recreate the
                                  collection); persist=True keeps the collection.
                                  user_id metadata := item["domain"] (the world).
    observe(i, text)              sessions leaving the window are buffered up to
                                  `window_tokens` (MemReader's chat-window size,
                                  default 1024) and then extracted in one call:
                                  GeneralTextMemory.extract([{role: user, content}])
                                  -> TextualMemoryItems (key / value / tags), which
                                  are embedded and upserted with .add().  This is
                                  how MOS wraps a plain string for extraction
                                  ([[{"role": "user", "content": memory_content}]]).
    recall(task, budget)          flush the buffer, then GeneralTextMemory.search(
                                  task, top_k) -> numbered "## Memories:" list in
                                  MOS._build_system_prompt's format, cut to budget.
    record_action(...)            the agent's own action is added verbatim as one
                                  memory item, exactly as MOS.add(memory_content=..)
                                  does for a general_text cube (no LLM call).
    end_episode()                 flush the buffer.
    stats()                       item count and call counters.

Seams (the only places this differs from the library as shipped)
    * LLM: a `revoke` backend registered in LLMFactory / LLMConfigFactory whose
      generate() calls self.llm.text(), so extraction runs on the backbone under
      test and is metered.  Embedder: a `revoke` backend in EmbedderFactory that
      calls self.llm.embed().  Vector DB: QdrantVecDB subclass whose only change
      is QdrantClient(location=":memory:") -- in-process, nothing on disk.
    * Malformed extraction output.  GeneralTextMemory.extract raises when the
      model's JSON lacks a key; MemOS's MemReader instead salvages the raw text as
      one memory item (simple_struct.py, bug #1355 note).  We do the same in two
      steps: re-parse the model's own reply with MemOS's parse_json_result and
      accept items with missing key/tags; if there is no "memory list" at all,
      store the raw window as one item (key = text[:10], tags []), as the reader
      does.  No second LLM call is made.
    * Multi-party transcripts are handed to the extractor as a single "user"
      message (MOS's convention for strings); the prompt's user/assistant
      perspective is left untouched.  No dedup / conflict handling exists in the
      general_text pipeline, so a rule and its later revocation coexist as
      separate items and both can be retrieved.

Unknown outcome.  MemOS has no success/failure branch in this pipeline: it
writes what it extracts and reads by similarity.  record_action stores the
action with no judgement attached; nothing here ever sees a label.

Configuration (self.cfg)
    top_k              12     memories retrieved per task (MOSConfig default is 5)
    window_tokens      1024   observe() buffer before one extraction call
    extract_max_tokens 2000   completion cap for the extraction call
    record_actions     True   add the agent's own action as a memory item
    show_session       False  append "[session N]" to each recalled memory
                              (not in MemOS; off by default)
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
import uuid
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# MemOS writes its log file (and any local state) under $MEMOS_BASE_PATH/.memos;
# keep that out of the repository.  Must be set before the package is imported.
os.environ.setdefault("MEMOS_BASE_PATH", os.path.join(tempfile.gettempdir(), "revoke_memos"))
os.makedirs(os.environ["MEMOS_BASE_PATH"], exist_ok=True)

from eval.memory.base import LLM, TOK, MemoryBackend, approx_tokens  # noqa: E402

# MemOS logs, at import, that its optional file parser and Nacos config are absent;
# neither is used here.  Real import failures still raise.
logging.disable(logging.WARNING)
try:
    import memos  # noqa: E402  (PyPI: MemoryOS)
finally:
    logging.disable(logging.NOTSET)

if not hasattr(memos, "MOS"):                                         # a stray module named memos
    raise ImportError("`memos` is not the MemoryOS package; pip install -r eval/memory/requirements-memos.txt")

from memos.configs.embedder import BaseEmbedderConfig, EmbedderConfigFactory  # noqa: E402
from memos.configs.llm import BaseLLMConfig, LLMConfigFactory                  # noqa: E402
from memos.configs.memory import MemoryConfigFactory                          # noqa: E402
from memos.configs.vec_db import QdrantVecDBConfig, VectorDBConfigFactory      # noqa: E402
from memos.embedders.base import BaseEmbedder                                 # noqa: E402
from memos.embedders.factory import EmbedderFactory                           # noqa: E402
from memos.llms.base import BaseLLM                                           # noqa: E402
from memos.llms.factory import LLMFactory                                     # noqa: E402
from memos.llms.utils import remove_thinking_tags                             # noqa: E402
from memos.memories.factory import MemoryFactory                              # noqa: E402
from memos.memories.textual.general import GeneralTextMemory                  # noqa: E402
from memos.memories.textual.item import TextualMemoryItem, TextualMemoryMetadata  # noqa: E402
from memos.vec_dbs.factory import VecDBFactory                                # noqa: E402
from memos.vec_dbs.qdrant import QdrantVecDB                                  # noqa: E402

# MemOS logs every add/search at INFO to its file handler, and every unparseable
# extraction reply as a multi-line console warning; stats() counts the latter
# (`lenient`, `salvaged`), so both are silenced here.
logging.getLogger("memos").setLevel(logging.WARNING)
logging.getLogger("memos.memories.textual.general").setLevel(logging.ERROR)

# --- the seams: MemOS backends that delegate to the shared REVOKE LLM ---------

_HANDLES: Dict[str, LLM] = {}
_LOCK = threading.Lock()
_SCHEME = "revoke://"


def _register(llm: LLM) -> str:
    handle = uuid.uuid4().hex
    with _LOCK:
        _HANDLES[handle] = llm
    return handle


def _lookup(model_name_or_path: str) -> LLM:
    if not model_name_or_path.startswith(_SCHEME):
        raise ValueError(f"revoke backend expects '{_SCHEME}<handle>', got {model_name_or_path!r}")
    with _LOCK:
        return _HANDLES[model_name_or_path[len(_SCHEME):]]


class RevokeLLMConfig(BaseLLMConfig):
    """MemOS LLM config whose model_name_or_path is 'revoke://<handle>'."""


class RevokeLLM(BaseLLM):
    """MemOS LLM backend: generate() is the backbone under test via LLM.text()."""

    def __init__(self, config: RevokeLLMConfig):
        self.config = config
        self.llm = _lookup(config.model_name_or_path)
        self.last_response = ""

    def generate(self, messages, **kwargs) -> str:
        out = self.llm.text(list(messages), max_tokens=int(kwargs.get("max_tokens", self.config.max_tokens)))
        if self.config.remove_think_prefix:
            out = remove_thinking_tags(out)
        self.last_response = out
        return out

    def generate_stream(self, messages, **kwargs):
        yield self.generate(messages, **kwargs)


class RevokeEmbedderConfig(BaseEmbedderConfig):
    """MemOS embedder config; model_name_or_path is 'revoke://<handle>'."""


class RevokeEmbedder(BaseEmbedder):
    """MemOS embedder backend: the harness's local embedder (LLM.embed)."""

    def __init__(self, config: RevokeEmbedderConfig):
        self.config = config
        self.llm = _lookup(config.model_name_or_path)

    def embed(self, texts):
        return self.llm.embed([str(t) for t in texts])


class InMemoryQdrantVecDB(QdrantVecDB):
    """MemOS's QdrantVecDB with the client opened in-process (':memory:').
    Everything else -- collection creation, search, add, count, delete -- is
    the parent class unchanged."""

    def __init__(self, config: QdrantVecDBConfig):
        from qdrant_client import QdrantClient

        self.config = config
        self._default_payload_index_fields = ["memory_type", "status", "vector_sync", "user_name"]
        self.client = QdrantClient(location=":memory:")
        self.create_collection()
        try:
            self.ensure_payload_indexes(self._default_payload_index_fields)
        except Exception:                                                 # noqa: BLE001
            pass


LLMConfigFactory.backend_to_class["revoke"] = RevokeLLMConfig
LLMFactory.backend_to_class["revoke"] = RevokeLLM
EmbedderConfigFactory.backend_to_class["revoke"] = RevokeEmbedderConfig
EmbedderFactory.backend_to_class["revoke"] = RevokeEmbedder
VectorDBConfigFactory.backend_to_class["qdrant_memory"] = QdrantVecDBConfig
VecDBFactory.backend_to_class["qdrant_memory"] = InMemoryQdrantVecDB


def _build_general_text_memory(handle: str, dim: int, extract_max_tokens: int) -> GeneralTextMemory:
    cfg = MemoryConfigFactory(backend="general_text", config={
        "extractor_llm": {"backend": "revoke", "config": {
            "model_name_or_path": _SCHEME + handle, "temperature": 0.0,
            "max_tokens": int(extract_max_tokens), "remove_think_prefix": True}},
        "vector_db": {"backend": "qdrant_memory", "config": {
            "collection_name": f"revoke_{handle}", "distance_metric": "cosine",
            "vector_dimension": int(dim), "path": ":memory:"}},
        "embedder": {"backend": "revoke", "config": {"model_name_or_path": _SCHEME + handle}},
    })
    with warnings.catch_warnings():
        # MemOS's factories model_dump() a config holding a model instance; pydantic warns
        warnings.simplefilter("ignore")
        mem = MemoryFactory.from_config(cfg)
    assert isinstance(mem, GeneralTextMemory)
    return mem


# --- the backend ----------------------------------------------------------------

class Backend(MemoryBackend):
    name = "memos"
    persist_across_episodes = True
    uses_llm = True
    recalls = True

    HEADER = ("You have access to conversation memories retrieved by MemOS from sessions that have left "
              "your context. Use them to understand the context, the rules in force and past interactions.\n\n"
              "## Memories:\n")

    def __init__(self, llm: LLM, cfg: Optional[Dict] = None):
        super().__init__(llm, cfg)
        self.top_k = int(self.cfg.get("top_k", 12))
        self.window_tokens = int(self.cfg.get("window_tokens", 1024))
        self.extract_max_tokens = int(self.cfg.get("extract_max_tokens", 2000))
        self.record_actions = bool(self.cfg.get("record_actions", True))
        self.show_session = bool(self.cfg.get("show_session", False))
        self.handle = _register(llm)
        dim = len(llm.embed(["dimension probe"])[0])
        self.mem = _build_general_text_memory(self.handle, dim, self.extract_max_tokens)
        self.user_id: Optional[str] = None
        self.pending: List[Tuple[int, str]] = []
        self.pending_tokens = 0
        self.n_extractions = 0
        self.n_lenient = 0
        self.n_salvaged = 0
        self.n_searches = 0
        self.n_action_items = 0

    # lifecycle --------------------------------------------------------------
    def begin_episode(self, item, persist=False):
        super().begin_episode(item, persist)
        self.user_id = str(item.get("domain") or item.get("id") or "world")
        if persist:
            self._flush()
        else:
            self.pending, self.pending_tokens = [], 0
            self.mem.delete_all()

    def observe(self, session_index, text):
        tk = approx_tokens(text)
        if self.pending and self.pending_tokens + tk > self.window_tokens:
            self._flush()
        self.pending.append((session_index, text))
        self.pending_tokens += tk
        if self.pending_tokens >= self.window_tokens:
            self._flush()

    def recall(self, task_text, budget_tokens):
        self._flush()
        if self.mem.vector_db.count() == 0:
            return ""
        items = self.mem.search(task_text, top_k=self.top_k)
        self.n_searches += 1
        if not items:
            return ""
        limit = budget_tokens * TOK
        lines: List[str] = []
        for i, it in enumerate(items, 1):
            line = f"{i}. {it.memory}"
            if self.show_session and it.metadata.session_id:
                line += f" [session {it.metadata.session_id}]"
            if lines and len(self.HEADER) + len("\n".join(lines + [line])) > limit:
                break
            lines.append(line)
        return self.clip(self.HEADER + "\n".join(lines), budget_tokens)

    def record_action(self, probe_id, task_text, action, rationale):
        if not self.record_actions:
            return
        you = (self.item or {}).get("you_prefix", "you")
        task = " ".join((task_text or "").split())[:200]
        why = " ".join((rationale or "").split())[:300]
        text = f"{you}: at task {probe_id} ({task}) chose `{action}`." + (f" {why}" if why else "")
        meta = TextualMemoryMetadata(user_id=self.user_id, session_id=f"task:{probe_id}", source="conversation")
        self.mem.add([TextualMemoryItem(memory=text, metadata=meta)])
        self.n_action_items += 1

    def end_episode(self):
        self._flush()

    def stats(self):
        return {"items": self.mem.vector_db.count(), "extractions": self.n_extractions,
                "lenient": self.n_lenient, "salvaged": self.n_salvaged,
                "searches": self.n_searches, "action_items": self.n_action_items}

    # extraction -------------------------------------------------------------
    def _flush(self):
        if not self.pending:
            return
        text = "\n".join(t for _, t in self.pending)
        idx = [i for i, _ in self.pending if i >= 0]
        sid = "" if not idx else (str(idx[0]) if len(idx) == 1 else f"{idx[0]}-{idx[-1]}")
        self.pending, self.pending_tokens = [], 0
        messages = [{"role": "user", "content": text}]
        items: Optional[List[TextualMemoryItem]] = None
        try:
            items = self.mem.extract(messages)                 # one LLM call, MemOS's prompt and parser
            self.n_extractions += 1
        except Exception:                                      # noqa: BLE001  malformed JSON, missing key, empty reply
            self.n_extractions += 1
            items = self._lenient_items(getattr(self.mem.extractor_llm, "last_response", ""))
            if items is None:
                items = self._salvage(text)
        for it in items:
            it.metadata.user_id = self.user_id
            it.metadata.session_id = sid or it.metadata.session_id
        if items:
            self.mem.add(items)

    def _lenient_items(self, raw: str) -> Optional[List[TextualMemoryItem]]:
        """Re-read the model's reply with MemOS's own parser, tolerating a missing
        key/tags.  None when there is no memory list at all."""
        if not raw:
            return None
        parsed = self.mem.parse_json_result(raw) or {}
        mem_list = parsed.get("memory list") if isinstance(parsed, dict) else None
        if not isinstance(mem_list, list):
            return None
        out = []
        for d in mem_list:
            if not isinstance(d, dict):
                continue
            value = str(d.get("value") or d.get("memory") or "").strip()
            if not value:
                continue
            tags = d.get("tags") if isinstance(d.get("tags"), list) else []
            out.append(TextualMemoryItem(memory=value, metadata={
                "key": str(d.get("key") or value[:10]), "source": "conversation",
                "tags": [str(t) for t in tags], "updated_at": datetime.now().isoformat()}))
        self.n_lenient += 1
        return out

    def _salvage(self, text: str) -> List[TextualMemoryItem]:
        """MemReader's fallback: the raw text becomes one memory item."""
        self.n_salvaged += 1
        return [TextualMemoryItem(memory=text, metadata={
            "key": text[:10], "source": "conversation", "tags": [],
            "updated_at": datetime.now().isoformat()})]
