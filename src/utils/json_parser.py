import json
import re
import ast
import logging
from typing import Any, Dict

logger = logging.getLogger("SafeJSONParser")


class SafeJSONParser:
    """
    Industrial-strength JSON parser for LLM outputs.

    Guarantees:
        - Never raises
        - Always returns valid JSON (dict)
        - Falls back to {"answer": raw_text} if needed
    """

    def __init__(self, max_size: int = 200_000):
        self.max_size = max_size

    # ============================================================
    # Public API
    # ============================================================

    def parse(self, llm_response: str) -> Dict[str, Any]:
        try:
            if not llm_response or not llm_response.strip():
                return self._fallback("")

            if len(llm_response) > self.max_size:
                return self._fallback(llm_response[:5000])

            normalized = self._normalize(llm_response)
            stripped = self._strip_code_fences(normalized)
            candidate = self._extract_json_block(stripped)

            # 1️⃣ Strict parse
            if candidate:
                try:
                    return self._ensure_dict(json.loads(candidate))
                except Exception:
                    pass

                # 2️⃣ Repair attempt
                repaired = self._repair(candidate)
                try:
                    return self._ensure_dict(json.loads(repaired))
                except Exception:
                    pass

                # 3️⃣ Python literal fallback
                try:
                    obj = ast.literal_eval(candidate)
                    return self._ensure_dict(obj)
                except Exception:
                    pass

            # 4️⃣ Final fallback
            return self._fallback(stripped)

        except Exception as e:
            logger.error("Unexpected parser failure: %s", e)
            return self._fallback(llm_response)

    # ============================================================
    # Utilities
    # ============================================================

    def _fallback(self, text: str) -> Dict[str, Any]:
        return {"answer": text.strip()}

    def _ensure_dict(self, obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            return {"answer": obj}
        return {"answer": str(obj)}

    def _normalize(self, text: str) -> str:
        text = text.replace("\x00", "")
        text = text.replace("\r\n", "\n")
        return text.strip()

    # ============================================================
    # Markdown Fence Removal
    # ============================================================

    def _strip_code_fences(self, text: str) -> str:
        fence_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
        matches = fence_pattern.findall(text)
        if matches:
            return max(matches, key=len).strip()
        return text

    # ============================================================
    # Balanced JSON Extraction
    # ============================================================

    def _extract_json_block(self, text: str):
        for i, ch in enumerate(text):
            if ch in "{[":
                block = self._balanced_substring(text, i)
                if block:
                    return block
        return None

    def _balanced_substring(self, text: str, start: int):
        stack = []
        in_string = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]

            if ch == '"' and not escape:
                in_string = not in_string

            if not in_string:
                if ch in "{[":
                    stack.append(ch)
                elif ch in "}]":
                    if not stack:
                        return None
                    stack.pop()
                    if not stack:
                        return text[start:i + 1]

            escape = (ch == "\\" and not escape)

        return None

    # ============================================================
    # Repair Layer (Safe Transformations Only)
    # ============================================================

    def _repair(self, text: str) -> str:
        text = self._remove_comments(text)
        text = self._remove_trailing_commas(text)
        text = self._fix_unquoted_keys(text)
        text = self._convert_python_literals(text)
        text = self._normalize_quotes(text)
        text = self._remove_control_chars(text)
        return text

    def _remove_comments(self, text: str) -> str:
        text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
        text = re.sub(r"#.*?$", "", text, flags=re.MULTILINE)
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        return text

    def _remove_trailing_commas(self, text: str) -> str:
        return re.sub(r",\s*([}\]])", r"\1", text)

    def _fix_unquoted_keys(self, text: str) -> str:
        return re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)', r'\1"\2"\3', text)

    def _convert_python_literals(self, text: str) -> str:
        text = re.sub(r"\bTrue\b", "true", text)
        text = re.sub(r"\bFalse\b", "false", text)
        text = re.sub(r"\bNone\b", "null", text)
        return text

    def _normalize_quotes(self, text: str) -> str:
        return re.sub(r"\'([^']*)\'", r'"\1"', text)

    def _remove_control_chars(self, text: str) -> str:
        return "".join(c for c in text if ord(c) >= 32 or c in "\n\t")
