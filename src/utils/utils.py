import ast
import json
import re
from typing import Any, List, Dict
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
