import os
import re
from enum import Enum
from typing import Optional, Union, List

class NamespaceTemplate(str, Enum):
    GLOBAL_DATA = "learning.data"

class NamespaceBuilder:

    VERSION = os.getenv("NAMESPACE_VERSION", "v1")
    DEFAULT_ROOT = os.getenv("DEFAULT_TENANT", "com")

    # ----------------------------------
    # Public Builders
    # ----------------------------------

    @classmethod
    def global_data(
            cls,
            path: Optional[Union[str, List[str]]] = None,
            tenant: Optional[str] = None,
    ) -> str:
        return cls._build(NamespaceTemplate.GLOBAL_DATA, path, tenant)

    # ----------------------------------
    # Core Builder
    # ----------------------------------

    @classmethod
    def _build(
            cls,
            template: NamespaceTemplate,
            path: Optional[Union[str, List[str]]] = None,
            tenant: Optional[str] = None,
    ) -> str:

        root = cls._sanitize(tenant or cls.DEFAULT_ROOT)
        namespace = cls._sanitize(template.value)

        parts = [root, namespace, cls.VERSION]

        if path:
            if isinstance(path, str):
                path = [path]

            for segment in path:
                parts.append(cls._sanitize(segment))

        return ".".join(parts)

    # ----------------------------------
    # Sanitizer
    # ----------------------------------

    @staticmethod
    def _sanitize(value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-z0-9_.-]", "-", value)
        return value.strip(".")
