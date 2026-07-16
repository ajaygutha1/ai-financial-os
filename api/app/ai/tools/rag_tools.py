from typing import Any

from sqlalchemy.orm import Session

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.provider.base import ToolDefinition
from app.ai.rag.retrieval import HybridRetriever

_CATEGORIES = ["emergency_fund", "debt", "retirement", "tax", "investing", "budgeting", "fraud"]


def build_rag_tool(db: Session, embeddings: EmbeddingProvider) -> ToolDefinition:
    """General financial-guidance lookup, distinct from analytics_tools.py's
    tools: those compute this user's own numbers, this searches reference
    material for concepts and best practices (what an emergency fund target
    should be, avalanche vs. snowball, how marginal tax brackets work, ...).
    """
    retriever = HybridRetriever(db, embeddings)

    def handler(tool_input: dict[str, Any]) -> dict[str, Any]:
        results = retriever.search(
            tool_input["query"], top_k=3, category=tool_input.get("category")
        )
        return {
            "results": [{"source_title": r.document_title, "content": r.content} for r in results]
        }

    return ToolDefinition(
        name="search_knowledge_base",
        description=(
            "Search a reference knowledge base of general personal-finance guidance: "
            "emergency funds, debt payoff strategies, retirement accounts, how tax "
            "brackets work, diversification/asset allocation, and budgeting "
            "frameworks. Use this for general concepts and best-practice guidance "
            "-- use the other tools for this specific user's own numbers."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for, in natural language.",
                },
                "category": {
                    "anyOf": [{"type": "string", "enum": _CATEGORIES}, {"type": "null"}],
                    "description": (
                        "Narrow the search to one topic area if it's obvious which "
                        "one applies, otherwise null to search everything."
                    ),
                },
            },
            "required": ["query", "category"],
            "additionalProperties": False,
        },
        handler=handler,
    )
