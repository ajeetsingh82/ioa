import ast
import json
import re
from typing import Any, List, Dict, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

def str_to_enum(enum_class, value):
    """
    Converts a string to an enum member.
    Returns None if the value is not a valid member.
    """
    try:
        return enum_class(value)
    except (ValueError, KeyError):
        return None

def try_extract_text_from_html(html: str) -> str:
    """
    Safely extracts clean text from an HTML string.
    Returns an empty string if parsing or text extraction fails for any reason.
    """
    if not html or not isinstance(html, str):
        return ""
        
    try:
        soup = BeautifulSoup(html, "html.parser")
        clean_text = soup.get_text(separator='\n', strip=True)
        return clean_text
    except Exception:
        # If any error occurs during parsing, return an empty string
        return ""

def extract_links(html: str, base_url: str) -> Set[str]:
    """
    Extracts and normalizes all links from an HTML string.
    Returns a set of absolute URLs.
    """
    if not html or not isinstance(html, str):
        return set()

    links = set()
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Normalize and join with base URL
            full_url = urljoin(base_url, href)
            
            # Basic validation: only keep http/https
            parsed = urlparse(full_url)
            if parsed.scheme in ["http", "https"]:
                # Remove fragment identifier
                clean_url = full_url.split("#")[0]
                links.add(clean_url)
    except Exception:
        pass
    
    return links

def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    Splits text into chunks of a specified size with overlap.
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - chunk_overlap
        
    return chunks

def parse_json_string(json_string: str) -> Any:
    """
    Safely parses a JSON string that might be enclosed in code fences.
    """
    # Remove potential markdown code fences
    if json_string.startswith("```json"):
        json_string = json_string[7:]
    if json_string.endswith("```"):
        json_string = json_string[:-3]
    
    json_string = json_string.strip()

    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        # Fallback for simple string responses that are not JSON
        return {"answer": json_string}

def get_thought_impressions(thought_content: str) -> List[str]:
    """
    Parses the 'impressions' list from a Thought's content string.
    """
    try:
        # The content is expected to be a string representation of a list
        impressions = ast.literal_eval(thought_content)
        if isinstance(impressions, list):
            return impressions
        return []
    except (ValueError, SyntaxError):
        return []

def clean_gateway_response(text: str) -> str:
    text = re.sub(r"<\|start_header_id\|>.*?<\|end_header_id\|>", "", text, flags=re.S)
    text = re.sub(r"<\|.*?\|>", "", text)
    return text.strip()
