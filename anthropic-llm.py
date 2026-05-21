#!/usr/bin/env python3
"""
anthropic-llm.py — Anthropic Messages API를 git-adr의 --llm-cmd로 사용하기 위한 래퍼.

stdin으로 프롬프트를 받아 Anthropic Messages API로 전달하고 stdout으로 결과 출력.

환경변수:
  ANTHROPIC_API_KEY  — 필수
  ANTHROPIC_MODEL    — 선택 (기본: claude-sonnet-4-6)

사용법:
  python git-adr.py --repo /path/to/repo --target implementation \
    --output ./adr-output/ \
    --llm-cmd "python /path/to/anthropic-llm.py"
"""

import json
import os
import sys
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("오류: ANTHROPIC_API_KEY 환경변수가 필요합니다.", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    prompt = sys.stdin.read()
    if not prompt.strip():
        sys.exit(0)

    payload = json.dumps({
        "model": model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"API 오류 ({e.code}): {body}", file=sys.stderr)
        sys.exit(1)

    # content 블록에서 텍스트 추출
    content = data.get("content", [])
    text_parts = [block["text"] for block in content if block.get("type") == "text"]
    print("\n".join(text_parts), end="")


if __name__ == "__main__":
    main()
