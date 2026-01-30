import os
import pandas as pd
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

class RAG:
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    LLM_MODEL = "gemini-3-flash-preview"
    
    def __init__(
        self,
        collection_name: str,
        dataset: pd.DataFrame,
        embed_field: list[str]
    ):
        """
        Initialize Qdrant RAG system.
        
        Args:
            collection_name: Name of the Qdrant collection
            embedding_model: Sentence transformer model for embeddings
            llm_model: LLM model for generation
        """
        if len(embed_field) == 0:
            raise ValueError("At least one field must be specified for embedding.")
        
        self.collection_name = collection_name
        self.dataset = dataset
        self.embedder = SentenceTransformer(self.EMBEDDING_MODEL, device="cpu")
        
        # Init vector store
        self.qdrant = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
        try:
            self.qdrant.get_collection(collection_name)
        except Exception:
            points = []
            
            for _, row in dataset.iterrows():
                embed_parts = []
                
                for field in embed_field:
                    if dataset[field].dtype != "string":
                        raise ValueError(f"Field '{field}' must be of string type.")
                    
                    embed_parts.append(f"{field}: {row[field]}")
                
                points.append(PointStruct(
                    id=str(uuid.uuid4()),  # Assuming the index can be used as the point ID
                    vector=self.embedder.encode("\n".join(embed_parts)).tolist(),
                    payload=row.to_dict()
                ))
            
            self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.embedder.get_sentence_embedding_dimension(),
                    distance=Distance.COSINE
                )
            )
            self.qdrant.upload_points(
                collection_name=collection_name,
                points=points
            )
            
    def search(self, query: str, limit: int = 5) -> pd.DataFrame:
        """
        Search for relevant documents.
        
        Args:
            query: Search query
            limit: Number of results to return
            
        Returns:
            pd.DataFrame: DataFrame of relevant documents with scores
        """
        # if not self.is_initialized:
        #     raise ValueError("Collection not initialized. Please index data first.")
        
        # Embed query
        query_vector = self.embedder.encode(query).tolist()
        
        # Search in Qdrant
        results = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True
        )
        
        rows = []
        
        for point in results.points:
            rows.append(point.payload)
          
        return pd.DataFrame(rows)  
        