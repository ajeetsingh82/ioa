from ddgs import DDGS # Updated import to use the new library

def search_web(query: str, max_results: int = 1) -> str:
    """
    Performs a web search using DuckDuckGo and returns the content
    of the first search result as cleaned text.
    """
    print(f"[Web Search] Searching for: '{query}'")
    
    try:
        # DDGS().text() returns a list of dictionaries, each containing
        # the title, href, and body (content) of a search result.
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            print("[Web Search] No results found.")
            return "No relevant information found from the web search."
            
        # We only need the content of the first result for our RAG agent.
        first_result_content = results[0].get('body', '')
        
        if not first_result_content:
            print("[Web Search] First result has no readable content.")
            return "The first search result could not be read."
            
        print(f"[Web Search] Retrieved content from: {results[0].get('href', 'Unknown URL')}")
        
        # The text is already reasonably clean, but we'll limit its length.
        return first_result_content[:3000]

    except Exception as e:
        print(f"[Web Search] An error occurred: {e}")
        return f"An error occurred during the web search: {e}"
