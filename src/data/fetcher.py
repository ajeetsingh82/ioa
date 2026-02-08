from ddgs import DDGS
import contextlib
import os
import logging
from typing import List, Dict

# Configure logger for the fetcher
logger = logging.getLogger("WebFetcher")

def search_web_ddg(query: str, max_results: int = 3) -> List[Dict]:
    """
    Performs a web search using DuckDuckGo and returns a list of result dictionaries.
    """
    if not query or not query.strip():
        logger.warning("Web search requested with empty query.")
        return []

    logger.info(f"Performing DDG web search for: '{query}'")
    
    try:
        with DDGS() as ddgs:
            # ddgs.text returns a generator, so we convert it to a list
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            logger.info("No results found from DDG web search.")
            return []
            
        logger.info(f"Retrieved {len(results)} results from DDG.")
        return results

    except Exception as e:
        logger.error(f"An error occurred during the DDG web search: {e}", exc_info=True)
        return []

def search_web(query: str, max_results: int = 3) -> str:
    """
    DEPRECATED: Performs a web search and returns a single concatenated string.
    Use search_web_ddg for a list of results.
    """
    logger.warning("The 'search_web' function is deprecated. Use 'search_web_ddg' instead.")
    results = search_web_ddg(query, max_results=max_results)
    
    if not results:
        return "No relevant information found from the web search."
    
    full_content = ""
    for i, result in enumerate(results):
        content = result.get('body', '')
        if content:
            full_content += f"--- Result {i+1} from {result.get('href', 'Unknown URL')} ---\n{content}\n\n"
    
    if not full_content:
        return "No readable content could be extracted from the search results."
        
    return full_content[:8000]
