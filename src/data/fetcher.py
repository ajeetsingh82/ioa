from ddgs import DDGS
import contextlib
import os

def search_web(query: str, max_results: int = 3) -> str:
    """
    Performs a web search using DuckDuckGo and returns the concatenated
    content of the top search results as cleaned text.
    """
    print(f"[Web Search] Searching for: '{query}'")
    
    try:
        # Suppress the noisy output from the ddgs library
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            print("[Web Search] No results found.")
            return "No relevant information found from the web search."
        
        # Concatenate the content of all results
        full_content = ""
        for i, result in enumerate(results):
            content = result.get('body', '')
            if content:
                full_content += f"--- Result {i+1} from {result.get('href', 'Unknown URL')} ---\n{content}\n\n"
        
        if not full_content:
            print("[Web Search] No readable content found in any results.")
            return "No readable content could be extracted from the search results."
            
        print(f"[Web Search] Retrieved and concatenated content from {len(results)} URLs.")
        
        # Limit the total length to avoid overwhelming the LLM
        return full_content[:8000]

    except Exception as e:
        print(f"[Web Search] An error occurred: {e}")
        return f"An error occurred during the web search: {e}"
