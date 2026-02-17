from __future__ import annotations

import re

_REPRO_KEYWORDS = re.compile(
    r"(steps\s+to\s+reproduce|how\s+to\s+reproduce|reproduction\s+steps|"
    r"repro\s+steps|minimal\s+reproduc|expected\s+behavio[ur]|actual\s+behavio[ur])",
    re.IGNORECASE,
)
_CODE_BLOCK = re.compile(r"```[\s\S]*?```")
_STACK_TRACE = re.compile(
    r"(Traceback \(most recent call last\)|at .+\(.+:\d+\)|"
    r"Error:.*\n\s+at |Exception in thread|panic:|FATAL ERROR)",
    re.IGNORECASE,
)
_EXPECTED_VS_ACTUAL = re.compile(
    r"(expected\s*(behavio[ur]|result|output)|actual\s*(behavio[ur]|result|output)|"
    r"expected:.*actual:|got:.*expected:)",
    re.IGNORECASE,
)
_ENV_DETAIL = re.compile(
    r"(node[. ]?v?\d|python\s*\d|npm\s*v?\d|os[:\s]|platform[:\s]|"
    r"version[:\s]|browser[:\s]|chrome\s*\d|firefox\s*\d|safari\s*\d|"
    r"windows|macos|linux|ubuntu|docker)",
    re.IGNORECASE,
)


def has_reproduction_info(body: str | None) -> bool:
    if not body:
        return False
    has_keywords = bool(_REPRO_KEYWORDS.search(body))
    has_code = bool(_CODE_BLOCK.search(body))
    return has_keywords and has_code


def extract_features(body: str | None) -> dict:
    """Extract structured features from issue body text."""
    if not body:
        return {
            "has_steps_to_reproduce": False,
            "has_expected_vs_actual": False,
            "has_stack_trace": False,
            "has_code_block": False,
            "env_detail_count": 0,
        }

    return {
        "has_steps_to_reproduce": bool(_REPRO_KEYWORDS.search(body)),
        "has_expected_vs_actual": bool(_EXPECTED_VS_ACTUAL.search(body)),
        "has_stack_trace": bool(_STACK_TRACE.search(body)),
        "has_code_block": bool(_CODE_BLOCK.search(body)),
        "env_detail_count": len(_ENV_DETAIL.findall(body)),
    }
