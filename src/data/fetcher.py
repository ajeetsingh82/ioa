from ddgs import DDGS
import contextlib
import os
import logging

# Configure logger for the fetcher
logger = logging.getLogger("WebFetcher")

def search_web(query: str, max_results: int = 3) -> str:
    """
    Performs a web search using DuckDuckGo and returns the concatenated
    content of the top search results as cleaned text.
    """
    if not query or not query.strip():
        logger.warning("Web search requested with empty query.")
        return "No search performed: Query was empty."

    logger.debug(f"Performing web search for: '{query}'")
    
    try:
        # Suppress the noisy output from the ddgs library
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            logger.debug("No results found from web search.")
            return "No relevant information found from the web search."
        
        # Concatenate the content of all results
        full_content = ""
        for i, result in enumerate(results):
            content = result.get('body', '')
            if content:
                full_content += f"--- Result {i+1} from {result.get('href', 'Unknown URL')} ---\n{content}\n\n"
        
        if not full_content:
            logger.debug("No readable content found in any of the search results.")
            return "No readable content could be extracted from the search results."
            
        logger.debug(f"Retrieved and concatenated content from {len(results)} URLs.")
        
        # Limit the total length to avoid overwhelming the LLM
        return full_content[:8000]

    except Exception as e:
        logger.error(f"An error occurred during the web search: {e}", exc_info=True)
        return f"An error occurred during the web search: {e}"
