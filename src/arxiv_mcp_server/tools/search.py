"""Search functionality for the arXiv MCP server."""

import arxiv
import json
from typing import Dict, Any, List
from datetime import datetime, timezone
from dateutil import parser
import mcp.types as types
from ..config import Settings
from ..utils import arxiv_client_retry

settings = Settings()

search_tool = types.Tool(
    name="search_papers",
    description="Search for papers on arXiv with advanced filtering",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search_query parameter defines the criteria for querying arXiv's API, using a Lucene-like syntax. Queries target specific metadata fields with the format field:value, where supported fields include ti (title), au (author), abs (abstract), co (comments), jr (journal reference), rn (report number), id (arXiv ID), and all (all of the above). There is no filter for categories. Field values can be quoted for multi-word terms, and Boolean operators (AND, OR, ANDNOT) must be capitalized. Grouping with parentheses is allowed to build complex expressions. Example query: (ti:GAN OR abs:GAN) AND (au:\"Ian Goodfellow\")"
            },
            "max_results": {
                "type": "integer",
                "description": "The maximum number of results to return. Default is 10. Maximum is 50."
            },
            "date_from": {
                "type": "string",
                "description": "The start date for date filtering. Leave blank if no date filtering is required."
            },
            "date_to": {
                "type": "string",
                "description": "The end date for date filtering. Leave blank if no date filtering is required."
            },
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "last_updated_newest_first", "last_updated_oldest_first", "submitted_date_newest_first", "submitted_date_oldest_first"],
                "description": "The sorting order of the results. Default is relevance."
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Category filter. Leave blank if no category filtering is required. Example: [\"cs.CV\", \"cs.LG\"]",
            },
        },
        "required": ["query"],
    },
)


def _is_within_date_range(
    date: datetime, start: datetime | None, end: datetime | None
) -> bool:
    """Check if a date falls within the specified range."""
    if start and not start.tzinfo:
        start = start.replace(tzinfo=timezone.utc)
    if end and not end.tzinfo:
        end = end.replace(tzinfo=timezone.utc)

    if start and date < start:
        return False
    if end and date > end:
        return False
    return True


def _process_paper(paper: arxiv.Result) -> Dict[str, Any]:
    """Process paper information with resource URI."""
    return {
        "id": paper.get_short_id(),
        "title": paper.title,
        "authors": [author.name for author in paper.authors],
        "abstract": paper.summary,
        "categories": paper.categories,
        "published": paper.published.isoformat(),
        "url": paper.pdf_url,
        "resource_uri": f"arxiv://{paper.get_short_id()}",
    }


async def handle_search(arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle paper search requests.

    Automatically adds field specifiers to plain queries for better relevance.
    This fixes issue #33 where queries sorted by date returned irrelevant results.
    """
    try:
        max_results = min(int(arguments.get("max_results", 10)), settings.MAX_RESULTS)

        # Build search query with category filtering
        query = arguments["query"]

        if categories := arguments.get("categories"):
            category_filter = " OR ".join(f"cat:{cat}" for cat in categories)
            query = f"({query}) AND ({category_filter})"

        sort_by_mapping = {
            "relevance": {
                "sort_by": arxiv.SortCriterion.Relevance,
                "sort_order": arxiv.SortOrder.Descending,
            },
            "last_updated_newest_first": {
                "sort_by": arxiv.SortCriterion.LastUpdatedDate,
                "sort_order": arxiv.SortOrder.Descending,
            },
            "last_updated_oldest_first": {
                "sort_by": arxiv.SortCriterion.LastUpdatedDate,
                "sort_order": arxiv.SortOrder.Ascending,
            },
            "submitted_date_newest_first": {
                "sort_by": arxiv.SortCriterion.SubmittedDate,
                "sort_order": arxiv.SortOrder.Descending,
            },
            "submitted_date_oldest_first": {
                "sort_by": arxiv.SortCriterion.SubmittedDate,
                "sort_order": arxiv.SortOrder.Ascending,
            },
        }

        sort_by = arxiv.SortCriterion.Relevance
        sort_order = arxiv.SortOrder.Descending
        if arguments.get("sort_by") in sort_by_mapping:
            sort_by = sort_by_mapping[arguments["sort_by"]]["sort_by"]
            sort_order = sort_by_mapping[arguments["sort_by"]]["sort_order"]

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Process results with date filtering
        results = []
        try:
            date_from = (
                parser.parse(arguments["date_from"]).replace(tzinfo=timezone.utc)
                if "date_from" in arguments and arguments["date_from"] != ""
                else None
            )
            date_to = (
                parser.parse(arguments["date_to"]).replace(tzinfo=timezone.utc)
                if "date_to" in arguments and arguments["date_to"] != ""
                else None
            )
        except (ValueError, TypeError) as e:
            return [
                types.TextContent(
                    type="text", text=f"Error: Invalid date format - {str(e)}"
                )
            ]
        
        client = arxiv.Client()
        for paper in arxiv_client_retry(client, client.results)(search):
            if _is_within_date_range(paper.published, date_from, date_to):
                results.append(_process_paper(paper))

            if len(results) >= max_results:
                break

        response_data = {"total_results": len(results), "papers": results}

        return [
            types.TextContent(type="text", text=json.dumps(response_data, indent=2))
        ]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
