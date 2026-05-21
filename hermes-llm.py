#!/usr/bin/env python3
"""
hermes-llm.py — Hermes CLI를 git-adr의 --llm-cmd로 사용하기 위한 래퍼.

stdin으로 프롬프트를 받아 hermes -z로 전달하고 stdout으로 결과 출력.

사용법:
  python git-adr.py --repo /path/to/repo --target impl-backend \
    --output ./adr-output/ \
    --llm-cmd "python /path/to/hermes-llm.py"
"""

import subprocess
import sys
import tempfile
import os

def main():
    prompt = sys.stdin.read()
    if not prompt.strip():
        sys.exit(0)

    # 프롬프트가 길면 임시 파일 경유
    # hermes -z 인자 길이 제한을 피하기 위해 파일 기반으로 처리
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(prompt)
        tmpfile = f.name

    try:
        # hermes -z @file 형식 시도, 없으면 직접 전달
        result = subprocess.run(
            ["hermes", "-z", f"@{tmpfile}"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0 or not result.stdout.strip():
            # fallback: 직접 전달 (짧은 프롬프트에만 동작)
            result = subprocess.run(
                ["hermes", "-z", prompt[:8000]],
                capture_output=True,
                text=True,
                timeout=180,
            )
        print(result.stdout, end='')
        if result.returncode != 0:
            sys.exit(result.returncode)
    finally:
        os.unlink(tmpfile)


if __name__ == "__main__":
    main()
