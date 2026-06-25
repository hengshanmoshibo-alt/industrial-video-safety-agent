from aicoding_shared.config import get_settings


class VectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._available = False
        self._client = None
        try:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=f"http://{self.settings.milvus_host}:{self.settings.milvus_port}")
            if not self._client.has_collection(self.settings.milvus_collection):
                self._client.create_collection(
                    collection_name=self.settings.milvus_collection,
                    dimension=128,
                    metric_type="COSINE",
                    consistency_level="Strong",
                )
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def upsert(self, rows: list[dict]) -> None:
        if not self._available or not rows:
            return
        self._client.upsert(collection_name=self.settings.milvus_collection, data=rows)

    def delete_chunks(self, chunk_ids: list[int]) -> None:
        if not self._available or not chunk_ids:
            return
        expr = "chunk_id in [" + ",".join(str(item) for item in chunk_ids) + "]"
        self._client.delete(collection_name=self.settings.milvus_collection, filter=expr)

    def search(self, vector: list[float], tenant_id: int, limit: int = 5) -> list[dict]:
        if not self._available:
            return []
        try:
            result = self._client.search(
                collection_name=self.settings.milvus_collection,
                data=[vector],
                limit=limit,
                filter=f"tenant_id == {tenant_id}",
                output_fields=["chunk_id", "document_id", "title", "category", "content", "source"],
            )
        except Exception:
            return []
        return [
            hit.get("entity", {}) | {"vector_score": round(float(hit.get("distance", 0) or 0), 4)}
            for hit in (result[0] if result else [])
        ]


def check_milvus() -> bool:
    return VectorStore().available
