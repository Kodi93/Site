"""Tests for the Netlify marketplace account deletion handler."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

EXPECTED_TOKEN = "gdel1f4f2f7c9b0a4f2e86b0bb7fb6c0f1a5"
FUNCTION_PATH = Path(__file__).resolve().parents[1] / "netlify/functions/accountDeletion.js"


def invoke_handler(event: dict, env: dict[str, str] | None = None) -> dict:
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

    run_env = os.environ.copy()
    run_env.setdefault("ACCOUNT_DELETION_TOKEN", EXPECTED_TOKEN)
    if env:
        run_env.update(env)

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env=run_env,
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


def sign_payload(payload: str) -> str:
    """Return the base64-encoded HMAC signature for the payload."""

    digest = hmac.new(
        EXPECTED_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("ascii")


@pytest.fixture()
def account_store_stub(tmp_path: Path) -> Path:
    stub_path = tmp_path / "accountStoreStub.js"
    stub_path.write_text(
        textwrap.dedent(
            """
            const fs = require('fs/promises');

            async function deleteUserById(id) {
              const logPath = process.env.ACCOUNT_STORE_LOG;
              if (logPath) {
                await fs.writeFile(logPath, JSON.stringify({ id }), 'utf8');
              }
              const mode = process.env.ACCOUNT_STORE_MODE || 'success';
              if (mode === 'not-found') {
                return false;
              }
              if (mode === 'error') {
                throw new Error('Simulated deletion failure');
              }
              return true;
            }

            module.exports = { deleteUserById };
            """
        )
    )
    return stub_path


def test_post_missing_signature_is_rejected() -> None:
    """POST requests without a signature must be rejected."""

    event = {
        "httpMethod": "POST",
        "headers": {},
        "body": "",
        "isBase64Encoded": False,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 403
    assert json.loads(result["body"]) == {"message": "Forbidden"}


def test_post_invalid_signature_is_rejected() -> None:
    """POST requests with an incorrect signature should be rejected."""

    payload = json.dumps({"userId": "123"})
    event = {
        "httpMethod": "POST",
        "headers": {"x-ebay-signature": "sha256=invalid"},
        "body": payload,
        "isBase64Encoded": False,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 403
    assert json.loads(result["body"]) == {"message": "Forbidden"}


def test_post_valid_signature_returns_204() -> None:
    """Valid signatures should allow the payload to be acknowledged."""

    payload = json.dumps({"userId": "abc-123"})
    signature = sign_payload(payload)
    event = {
        "httpMethod": "POST",
        "headers": {"x-ebay-signature": f"sha256={signature}"},
        "body": payload,
        "isBase64Encoded": False,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 204
    assert result["body"] == ""


def test_post_valid_signature_handles_base64_body() -> None:
    """Signatures must be verified against the decoded payload."""

    payload = json.dumps({"userId": "encoded"})
    signature = sign_payload(payload)
    encoded_body = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    event = {
        "httpMethod": "POST",
        "headers": {"x-ebay-signature": signature},
        "body": encoded_body,
        "isBase64Encoded": True,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 204
    assert result["body"] == ""


def test_post_legacy_token_header_still_allows_request() -> None:
    """Fallback token header support eases manual testing flows."""

    payload = json.dumps({"userId": "legacy"})
    event = {
        "httpMethod": "POST",
        "headers": {"x-verification-token": EXPECTED_TOKEN},
        "body": payload,
        "isBase64Encoded": False,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 204
    assert result["body"] == ""


def test_post_missing_user_identifier_returns_400() -> None:
    payload = json.dumps({"note": "no id"})
    signature = sign_payload(payload)
    event = {
        "httpMethod": "POST",
        "headers": {"x-ebay-signature": f"sha256={signature}"},
        "body": payload,
        "isBase64Encoded": False,
    }

    result = invoke_handler(event)
    assert result["statusCode"] == 400
    assert json.loads(result["body"]) == {"message": "Missing user identifier in payload"}



def test_post_valid_signature_triggers_deletion(account_store_stub: Path, tmp_path: Path) -> None:
    payload = json.dumps({"userId": "abc-123"})
    signature = sign_payload(payload)
    log_path = tmp_path / "deletion-log.json"
    env = {
        "ACCOUNT_STORE_MODULE": account_store_stub.as_posix(),
        "ACCOUNT_STORE_LOG": log_path.as_posix(),
    }
    event = {
        "httpMethod": "POST",
        "headers": {"x-ebay-signature": f"sha256={signature}"},
        "body": payload,
        "isBase64Encoded": False,
    }

    result = invoke_handler(event, env=env)
    assert result["statusCode"] == 204
    assert result["body"] == ""
    assert log_path.exists()
    assert json.loads(log_path.read_text(encoding="utf-8")) == {"id": "abc-123"}



def test_post_unknown_user_returns_404(account_store_stub: Path, tmp_path: Path) -> None:
    payload = json.dumps({"userId": "ghost"})
    signature = sign_payload(payload)
    log_path = tmp_path / "not-found-log.json"
    env = {
        "ACCOUNT_STORE_MODULE": account_store_stub.as_posix(),
        "ACCOUNT_STORE_LOG": log_path.as_posix(),
        "ACCOUNT_STORE_MODE": "not-found",
    }
    event = {
        "httpMethod": "POST",
        "headers": {"x-ebay-signature": f"sha256={signature}"},
        "body": payload,
        "isBase64Encoded": False,
    }

    result = invoke_handler(event, env=env)
    assert result["statusCode"] == 404
    assert json.loads(result["body"]) == {"message": "Account not found"}
    assert json.loads(log_path.read_text(encoding="utf-8")) == {"id": "ghost"}



def test_post_deletion_failure_returns_500(account_store_stub: Path, tmp_path: Path) -> None:
    payload = json.dumps({"userId": "error-user"})
    signature = sign_payload(payload)
    log_path = tmp_path / "error-log.json"
    env = {
        "ACCOUNT_STORE_MODULE": account_store_stub.as_posix(),
        "ACCOUNT_STORE_LOG": log_path.as_posix(),
        "ACCOUNT_STORE_MODE": "error",
    }
    event = {
        "httpMethod": "POST",
        "headers": {"x-ebay-signature": f"sha256={signature}"},
        "body": payload,
        "isBase64Encoded": False,
    }

    result = invoke_handler(event, env=env)
    assert result["statusCode"] == 500
    assert json.loads(result["body"]) == {"message": "Failed to delete account"}
    assert json.loads(log_path.read_text(encoding="utf-8")) == {"id": "error-user"}
