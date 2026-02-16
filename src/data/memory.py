import os
import uuid
import logging
from typing import List, Dict, Optional, Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions

from ..model.agent_model_registry import model_registry
from ..model.agent_types import AgentType

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class MemoryError(Exception):
    pass


class Memory:
    """
    Production-grade ChromaDB DAO.

    Responsibilities:
    - Connection management
    - Collection management
    - CRUD operations
    - Vector search
    - Metadata filtering
    - Namespace prefix filtering
    - Structured output normalization
    """

    def __init__(
            self,
            chroma_url: Optional[str] = None,
            embedding_function: Optional[Any] = None,
            batch_size: Optional[int] = None,
    ):

        self.chroma_url = chroma_url or os.getenv("CHROMA_URL", "http://localhost:8000")
        self.batch_size = batch_size or int(os.getenv("CHROMA_BATCH_SIZE", "500"))

        # ----------------------------------
        # Embedding Function Resolution
        # ----------------------------------
        if embedding_function is None:
            semantics_config = model_registry.get_agent_model_config(AgentType.SEMANTICS)

            if semantics_config.get("api_type") == "embeddings":
                endpoint = semantics_config.get("endpoint")
                base_url = endpoint.replace("/api/embeddings", "") if endpoint else "http://localhost:11434"

                self.embedding_function = embedding_functions.OllamaEmbeddingFunction(
                    url=base_url,
                    model_name=semantics_config.get("model", "nomic-embed-text"),
                )
            else:
                self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        else:
            self.embedding_function = embedding_function

        # ----------------------------------
        # Chroma Client
        # ----------------------------------
        try:
            self.client = chromadb.HttpClient(
                host=self._extract_host(self.chroma_url),
                port=self._extract_port(self.chroma_url),
                settings=chromadb.config.Settings(anonymized_telemetry=False)
            )
        except Exception as e:
            raise MemoryError(f"Failed to connect to ChromaDB at {self.chroma_url}: {e}")

        self._collections: Dict[str, Collection] = {}

    # =========================================================
    # Internal Utilities
    # =========================================================

    def _extract_host(self, url: str) -> str:
        return url.replace("http://", "").replace("https://", "").split(":")[0]

    def _extract_port(self, url: str) -> int:
        parts = url.replace("http://", "").replace("https://", "").split(":")
        return int(parts[1]) if len(parts) == 2 else 8000

    def _get_collection(self, collection_name: str) -> Collection:
        if collection_name not in self._collections:
            try:
                self._collections[collection_name] = self.client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function,
                )
            except Exception as e:
                logger.exception("Failed to get/create collection")
                raise MemoryError(str(e))
        return self._collections[collection_name]

    def _normalize_query_result(self, result: Dict) -> List[Dict]:
        if not result.get("ids"):
            return []

        normalized = []
        for i in range(len(result["ids"][0])):
            normalized.append({
                "id": result["ids"][0][i],
                "document": result["documents"][0][i],
                "metadata": result["metadatas"][0][i] if result.get("metadatas") else {},
                "distance": result["distances"][0][i] if result.get("distances") else None,
            })
        return normalized

    # =========================================================
    # Write Operations
    # =========================================================

    def add(
            self,
            collection_name: str,
            documents: List[str],
            metadatas: Optional[List[Dict]] = None,
            ids: Optional[List[str]] = None,
    ) -> List[str]:

        if not documents:
            return []

        collection = self._get_collection(collection_name)

        ids = ids or [str(uuid.uuid4()) for _ in documents]
        metadatas = metadatas or [{} for _ in documents]

        try:
            for i in range(0, len(documents), self.batch_size):
                end = min(i + self.batch_size, len(documents))
                collection.add(
                    documents=documents[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end],
                )
        except Exception as e:
            logger.exception("Add failed")
            raise MemoryError(str(e))

        return ids

    def upsert(
            self,
            collection_name: str,
            documents: List[str],
            metadatas: Optional[List[Dict]] = None,
            ids: Optional[List[str]] = None,
    ) -> List[str]:

        if not documents:
            return []

        collection = self._get_collection(collection_name)

        ids = ids or [str(uuid.uuid4()) for _ in documents]
        metadatas = metadatas or [{} for _ in documents]

        try:
            for i in range(0, len(documents), self.batch_size):
                end = min(i + self.batch_size, len(documents))
                collection.upsert(
                    documents=documents[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end],
                )
        except Exception as e:
            logger.exception("Upsert failed")
            raise MemoryError(str(e))

        return ids

    # =========================================================
    # Vector Search
    # =========================================================

    def query(
            self,
            collection_name: str,
            query_text: str,
            n_results: int = 5,
            where: Optional[Dict] = None,
    ) -> List[Dict]:

        collection = self._get_collection(collection_name)

        try:
            result = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where,
            )
        except Exception as e:
            logger.exception("Query failed")
            raise MemoryError(str(e))

        return self._normalize_query_result(result)

    # =========================================================
    # Namespace Helpers (Prefix-Based)
    # =========================================================

    def query_by_namespace_prefix(
            self,
            collection_name: str,
            namespace_prefix: str,
            query_text: Optional[str] = None,
            n_results: int = 5,
    ) -> List[Dict]:
        """
        Hybrid vector + namespace prefix search.
        Requires namespace stored in metadata.
        """

        where = {
            "namespace": {
                "$contains": namespace_prefix
            }
        }

        if query_text:
            return self.query(collection_name, query_text, n_results, where)

        return self.get_by_metadata(collection_name, where, limit=n_results)

    # =========================================================
    # Metadata Retrieval
    # =========================================================

    def get_by_id(self, collection_name: str, doc_id: str) -> Optional[Dict]:

        collection = self._get_collection(collection_name)

        try:
            result = collection.get(ids=[doc_id])
        except Exception as e:
            logger.exception("Get by ID failed")
            raise MemoryError(str(e))

        if not result.get("ids"):
            return None

        return {
            "id": result["ids"][0],
            "document": result["documents"][0],
            "metadata": result["metadatas"][0] if result.get("metadatas") else {},
        }

    def get_by_metadata(
            self,
            collection_name: str,
            where: Dict,
            limit: int = 100,
    ) -> List[Dict]:

        collection = self._get_collection(collection_name)

        try:
            result = collection.get(where=where, limit=limit)
        except Exception as e:
            logger.exception("Metadata retrieval failed")
            raise MemoryError(str(e))

        if not result.get("ids"):
            return []

        documents = []
        for i in range(len(result["ids"])):
            documents.append({
                "id": result["ids"][i],
                "document": result["documents"][i],
                "metadata": result["metadatas"][i] if result.get("metadatas") else {},
            })

        return documents

    # =========================================================
    # Document Type Helpers
    # =========================================================

    def get_by_type(
            self,
            collection_name: str,
            doc_type: str,
            limit: int = 100,
    ) -> List[Dict]:
        return self.get_by_metadata(
            collection_name,
            where={"doc_type": doc_type},
            limit=limit,
        )

    def get_by_namespace(
            self,
            collection_name: str,
            namespace: str,
            limit: int = 100,
    ) -> List[Dict]:
        return self.get_by_metadata(
            collection_name,
            where={"namespace": namespace},
            limit=limit,
        )

    # =========================================================
    # Delete / Count
    # =========================================================

    def delete(
            self,
            collection_name: str,
            ids: Optional[List[str]] = None,
            where: Optional[Dict] = None,
    ):
        collection = self._get_collection(collection_name)
        collection.delete(ids=ids, where=where)

    def count(self, collection_name: str) -> int:
        return self._get_collection(collection_name).count()

    # =========================================================
    # Health
    # =========================================================

    def health_check(self) -> bool:
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False


# Singleton
memory = Memory()
