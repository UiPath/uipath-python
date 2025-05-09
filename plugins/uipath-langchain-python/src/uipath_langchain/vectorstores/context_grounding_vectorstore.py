"""
Vector store implementation that connects to UiPath Context Grounding as a backend.

This is a read-only vector store that uses the UiPath Context Grounding API to retrieve documents.

You need to set the following environment variables (also see .env.example):
### - UIPATH_URL="https://alpha.uipath.com/{ORG_ID}/{TENANT_ID}"
### - UIPATH_ACCESS_TOKEN={BEARER_TOKEN_WITH_CONTEXT_GROUNDING_PERMISSIONS}
### - UIPATH_FOLDER_PATH="" - this can be left empty
### - UIPATH_FOLDER_KEY="" - this can be left empty
"""

from collections.abc import Iterable
from typing import Any, Optional, TypeVar

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from uipath import UiPath

VST = TypeVar("VST", bound="ContextGroundingVectorStore")


class ContextGroundingVectorStore(VectorStore):
    """Vector store that uses UiPath Context Grounding (ECS) as a backend.

    This class provides a straightforward implementation that connects to the
    UiPath Context Grounding API for semantic searching.

    Example:
        .. code-block:: python

            from uipath_agents_gym.tools.ecs_vectorstore import ContextGroundingVectorStore

            # Initialize the vector store with an index name
            vectorstore = ContextGroundingVectorStore(index_name="ECCN")

            # Perform similarity search
            docs_with_scores = vectorstore.similarity_search_with_score(
                "How do I process an invoice?", k=5
            )
    """

    def __init__(
        self,
        index_name: str,
        uipath_sdk: Optional[UiPath] = None,
    ):
        """Initialize the ContextGroundingVectorStore.

        Args:
            index_name: Name of the context grounding index to use
            uipath_sdk: Optional SDK instance to use. If not provided, a new instance will be created.
        """
        self.index_name = index_name
        self.sdk = uipath_sdk or UiPath()

    def similarity_search_with_score(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        """Return documents most similar to the query along with the distances.
        The distance is 1 - score, where score is the relevance score returned by the Context Grounding API.

        Args:
            query: The query string
            k: Number of results to return (default=4)

        Returns:
            list of tuples of (document, score)
        """
        # Call the UiPath SDK to perform the search
        results = self.sdk.context_grounding.search(
            name=self.index_name,
            query=query,
            number_of_results=k,
        )

        # Convert the results to Documents with scores
        docs_with_scores = []
        for result in results:
            # Create metadata from result fields
            metadata = {
                "source": result.source,
                "id": result.id,
                "reference": result.reference,
                "page_number": result.page_number,
                "source_document_id": result.source_document_id,
                "caption": result.caption,
            }

            # Add any operation metadata if available
            if result.metadata:
                metadata["operation_id"] = result.metadata.operation_id
                metadata["strategy"] = result.metadata.strategy

            # Create a Document with the content and metadata
            doc = Document(
                page_content=result.content,
                metadata=metadata,
            )

            score = 1.0 - float(result.score)

            docs_with_scores.append((doc, score))

        return docs_with_scores

    def similarity_search_with_relevance_scores(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        """Return documents along with their relevance scores on a scale from 0 to 1.

        This directly uses the scores provided by the Context Grounding API,
        which are already normalized between 0 and 1.

        Args:
            query: The query string
            k: Number of documents to return (default=4)

        Returns:
            list of tuples of (document, relevance_score)
        """
        return [
            (doc, 1.0 - score)
            for doc, score in self.similarity_search_with_score(query, k, **kwargs)
        ]

    async def asimilarity_search_with_score(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        """Asynchronously return documents most similar to the query along with scores.

        Args:
            query: The query string
            k: Number of results to return (default=4)

        Returns:
            list of tuples of (document, score)
        """
        # Call the UiPath SDK to perform the search asynchronously
        results = await self.sdk.context_grounding.search_async(
            name=self.index_name,
            query=query,
            number_of_results=k,
        )

        # Convert the results to Documents with scores
        docs_with_scores = []
        for result in results:
            # Create metadata from result fields
            metadata = {
                "source": result.source,
                "id": result.id,
                "reference": result.reference,
                "page_number": result.page_number,
                "source_document_id": result.source_document_id,
                "caption": result.caption,
            }

            # Add any operation metadata if available
            if result.metadata:
                metadata["operation_id"] = result.metadata.operation_id
                metadata["strategy"] = result.metadata.strategy

            # Create a Document with the content and metadata
            doc = Document(
                page_content=result.content,
                metadata=metadata,
            )

            # Get the distance score as 1 - ecs_score
            score = 1.0 - float(result.score)

            docs_with_scores.append((doc, score))

        return docs_with_scores

    async def asimilarity_search_with_relevance_scores(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        """Asynchronously return documents along with their relevance scores on a scale from 0 to 1.

        This directly uses the scores provided by the Context Grounding API,
        which are already normalized between 0 and 1.

        Args:
            query: The query string
            k: Number of documents to return (default=4)

        Returns:
            list of tuples of (document, relevance_score)
        """
        return [
            (doc, 1.0 - score)
            for doc, score in await self.asimilarity_search_with_score(
                query, k, **kwargs
            )
        ]

    def similarity_search(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[Document]:
        """Return documents most similar to the query.

        Args:
            query: The query string
            k: Number of results to return (default=4)

        Returns:
            list of documents most similar to the query
        """
        docs_and_scores = self.similarity_search_with_score(query, k, **kwargs)
        return [doc for doc, _ in docs_and_scores]

    async def asimilarity_search(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[Document]:
        """Asynchronously return documents most similar to the query.

        Args:
            query: The query string
            k: Number of results to return (default=4)

        Returns:
            list of documents most similar to the query
        """
        docs_and_scores = await self.asimilarity_search_with_score(query, k, **kwargs)
        return [doc for doc, _ in docs_and_scores]

    @classmethod
    def from_texts(
        cls: type[VST],
        texts: list[str],
        embedding: Embeddings,
        metadatas: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> VST:
        """This method is required by the VectorStore abstract class, but is not supported
        by ContextGroundingVectorStore which is read-only.

        Raises:
            NotImplementedError: This method is not supported by ContextGroundingVectorStore
        """
        raise NotImplementedError(
            "ContextGroundingVectorStore is a read-only wrapper for UiPath Context Grounding. "
            "Creating a vector store from texts is not supported."
        )

    # Other required methods with minimal implementation to satisfy the interface
    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> list[str]:
        """Not implemented for ContextGroundingVectorStore as this is a read-only wrapper."""
        raise NotImplementedError(
            "ContextGroundingVectorStore is a read-only wrapper for UiPath Context Grounding."
        )

    def delete(self, ids: Optional[list[str]] = None, **kwargs: Any) -> Optional[bool]:
        """Not implemented for ContextGroundingVectorStore as this is a read-only wrapper."""
        raise NotImplementedError(
            "ContextGroundingVectorStore is a read-only wrapper for UiPath Context Grounding."
        )
