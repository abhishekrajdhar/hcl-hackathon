"""Tolerant extraction of a JSON object from raw model text.

Models wrap JSON in prose or markdown fences, or emit trailing commentary. This
recovers the first balanced `{...}` object so validation gets a fair chance
before the repair path is triggered.
"""

from __future__ import annotations

import json
from typing import Any


class JsonExtractionError(ValueError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise JsonExtractionError("empty model output")

    cleaned = text.strip()
    # Strip a leading ```json / ``` fence if present.
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if cleaned.count("```") >= 2 else cleaned.strip("`")
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]

    # Fast path: the whole thing is a JSON object.
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Otherwise scan for the first balanced top-level object.
    start = cleaned.find("{")
    if start == -1:
        raise JsonExtractionError("no JSON object found in model output")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                snippet = cleaned[start : index + 1]
                try:
                    parsed = json.loads(snippet)
                except json.JSONDecodeError as exc:
                    raise JsonExtractionError(f"malformed JSON object: {exc}") from exc
                if not isinstance(parsed, dict):
                    raise JsonExtractionError("top-level JSON is not an object")
                return parsed
    raise JsonExtractionError("unbalanced JSON braces in model output")
