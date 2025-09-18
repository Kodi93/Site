"""Tests for the Netlify marketplace account deletion handler."""
from __future__ import annotations

import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

EXPECTED_TOKEN = "gdel1f4f2f7c9b0a4f2e86b0bb7fb6c0f1a5"
FUNCTION_PATH = Path(__file__).resolve().parents[1] / "netlify/functions/accountDeletion.js"


def invoke_handler(event: dict) -> dict:
    """Execute the Netlify handler in Node.js and return the JSON response."""

    script = textwrap.dedent(
        f"""
        const handler = require('{FUNCTION_PATH.as_posix()}').handler;
        const event = {json.dumps(event)};
        handler(event).then((result) => {{
          console.log(JSON.stringify(result));
        }}).catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert stdout_lines, f"Handler produced no output. stderr: {completed.stderr}"
    return json.loads(stdout_lines[-1])


def test_challenge_response_hashing() -> None:
    """Ensure the handler returns the expected response for challenge verification."""

    challenge_code = "abc123"
    endpoint_path = "/.netlify/functions/accountDeletion"
    endpoint_url = f"https://example.com{endpoint_path}"
    event = {
        "httpMethod": "GET",
        "queryStringParameters": {"challenge_code": challenge_code},
        "rawQuery": f"challenge_code={challenge_code}",
        "rawUrl": f"{endpoint_url}?challenge_code={challenge_code}",
        "headers": {"host": "example.com"},
        "path": endpoint_path,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 200
    assert result["headers"]["Content-Type"] == "application/json"

    body = json.loads(result["body"])
    expected_hash = hashlib.sha256(
        (challenge_code + EXPECTED_TOKEN + endpoint_url).encode("utf-8")
    ).hexdigest()
    assert body == {"challengeResponse": expected_hash}


def test_challenge_response_without_raw_url() -> None:
    """Verify fallback endpoint construction when rawUrl is unavailable."""

    challenge_code = "verify-me"
    endpoint_path = "/.netlify/functions/accountDeletion"
    endpoint_url = f"https://giftgrab.test{endpoint_path}"
    event = {
        "httpMethod": "GET",
        "queryStringParameters": {"challenge_code": challenge_code},
        "headers": {
            "host": "giftgrab.test",
            "x-forwarded-proto": "https",
        },
        "path": endpoint_path,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 200

    body = json.loads(result["body"])
    expected_hash = hashlib.sha256(
        (challenge_code + EXPECTED_TOKEN + endpoint_url).encode("utf-8")
    ).hexdigest()
    assert body == {"challengeResponse": expected_hash}


def test_health_check_ready_status() -> None:
    """GET without a challenge code should behave as a readiness probe."""

    event = {
        "httpMethod": "GET",
        "queryStringParameters": {},
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"status": "ready"}


def test_head_request_returns_empty_body() -> None:
    """HEAD requests should return a 200 with no response body."""

    event = {
        "httpMethod": "HEAD",
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 200
    assert result["body"] == ""


def test_post_invalid_token_is_rejected() -> None:
    """POST requests missing the verification token must be rejected."""

    event = {
        "httpMethod": "POST",
        "headers": {},
        "body": "",
        "isBase64Encoded": False,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 403
    assert json.loads(result["body"]) == {"message": "Forbidden"}
