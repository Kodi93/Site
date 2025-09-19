const crypto = require('crypto');
const { URL, URLSearchParams } = require('url');

const path = require('path');

const defaultAccountStorePath = path.resolve(
  process.cwd(),
  'netlify/lib/accountStore.cjs'
);

const accountStorePath = process.env.ACCOUNT_STORE_MODULE
  ? process.env.ACCOUNT_STORE_MODULE
  : defaultAccountStorePath;

const accountStoreModule = require(accountStorePath);

const { deleteUserById } = accountStoreModule;

if (typeof deleteUserById !== 'function') {
  throw new Error('Account store module must export a deleteUserById function.');
}

const REQUIRED_METHOD = 'POST';
const HEALTH_CHECK_METHODS = new Set(['GET', 'HEAD']);

const CHALLENGE_PARAM_KEYS = ['challenge_code', 'challengeCode'];
const SIGNATURE_HEADER_KEY = 'x-ebay-signature';

function normalizeHeaders(headers = {}) {
  const normalized = {};
  for (const [key, value] of Object.entries(headers)) {
    if (typeof value === 'string') {
      normalized[key.toLowerCase()] = value;
    }
  }
  return normalized;
}

function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') {
    return false;
  }

  const bufferA = Buffer.from(a, 'utf8');
  const bufferB = Buffer.from(b, 'utf8');
  if (bufferA.length !== bufferB.length) {
    return false;
  }

  return crypto.timingSafeEqual(bufferA, bufferB);
}

function extractSignatureValues(signatureHeader) {
  if (typeof signatureHeader !== 'string') {
    return [];
  }

  return signatureHeader
    .split(',')
    .map((segment) => segment.trim())
    .filter(Boolean)
    .map((segment) => {
      const match = segment.match(/^sha256=(.+)$/i);
      if (match) {
        return match[1].trim();
      }
      return segment;
    })
    .filter(Boolean);
}

function extractChallengeCode(event) {
  const query = event.queryStringParameters || {};
  for (const key of CHALLENGE_PARAM_KEYS) {
    if (typeof query[key] === 'string' && query[key]) {
      return query[key];
    }
  }

  if (event.rawQuery) {
    const params = new URLSearchParams(event.rawQuery);
    for (const key of CHALLENGE_PARAM_KEYS) {
      if (params.has(key)) {
        const value = params.get(key);
        if (value) {
          return value;
        }
      }
    }
  }

  return null;
}

function resolveEndpoint(event) {
  if (event.rawUrl) {
    try {
      const parsed = new URL(event.rawUrl);
      return `${parsed.origin}${parsed.pathname}`;
    } catch (error) {
      console.warn('Failed to parse rawUrl for challenge response.', error);
    }
  }

  const headers = normalizeHeaders(event.headers);
  const host = headers.host;
  const path = event.path || '';
  if (!host) {
    return path;
  }

  const protocol = headers['x-forwarded-proto'] || headers['x-forwarded_proto'] || 'https';
  return `${protocol}://${host}${path}`;
}

function jsonResponse(statusCode, body) {
  return {
    statusCode,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  };
}

function resolveUserIdFromPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const candidates = [
    payload.userId,
    payload.user_id,
    payload.accountId,
    payload.account_id,
    payload.id,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === 'string') {
      const trimmed = candidate.trim();
      if (trimmed) {
        return trimmed;
      }
    }
  }

  if (payload.user && typeof payload.user === 'object') {
    return resolveUserIdFromPayload(payload.user);
  }

  return null;
}

const handler = async (event) => {
  const method = event.httpMethod || '';
  const headers = normalizeHeaders(event.headers);
  const expectedToken = process.env.ACCOUNT_DELETION_TOKEN || '';

  if (method === 'GET') {
    const challengeCode = extractChallengeCode(event);
    if (challengeCode && expectedToken) {
      const endpoint = resolveEndpoint(event);
      const hash = crypto.createHash('sha256');
      hash.update(challengeCode);
      hash.update(expectedToken);
      hash.update(endpoint);
      const challengeResponse = hash.digest('hex');

      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ challengeResponse }),
      };
    }
  }

  if (HEALTH_CHECK_METHODS.has(method)) {
    const body = method === 'HEAD' ? '' : JSON.stringify({ status: 'ready' });

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
      },
      body,
    };
  }

  if (method !== REQUIRED_METHOD) {
    return {
      statusCode: 405,
      headers: {
        Allow: `${REQUIRED_METHOD}, GET, HEAD`,
      },
      body: JSON.stringify({ message: 'Method Not Allowed' }),
    };
  }

  if (!expectedToken) {
    console.error('ACCOUNT_DELETION_TOKEN is not configured. Rejecting request.');
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'Misconfigured function' }),
    };
  }

  const signatureValues = extractSignatureValues(headers[SIGNATURE_HEADER_KEY]);
  const verificationToken = headers['x-verification-token'];

  const rawBodyBuffer = event.isBase64Encoded
    ? Buffer.from(event.body || '', 'base64')
    : Buffer.from(event.body || '', 'utf8');
  const rawBody = rawBodyBuffer.toString('utf8');

  let requestIsAuthorized = false;

  if (signatureValues.length > 0) {
    try {
      const hmac = crypto.createHmac('sha256', expectedToken);
      hmac.update(rawBodyBuffer);
      const digestBuffer = hmac.digest();
      const expectedBase64 = digestBuffer.toString('base64');
      const expectedHex = digestBuffer.toString('hex');

      requestIsAuthorized = signatureValues.some((candidate) => {
        const trimmed = candidate.trim();
        return safeEqual(trimmed, expectedBase64) || safeEqual(trimmed, expectedHex);
      });
    } catch (error) {
      console.error('Failed to verify signature for deletion payload.', error);
      requestIsAuthorized = false;
    }
  }

  if (!requestIsAuthorized && typeof verificationToken === 'string') {
    requestIsAuthorized = safeEqual(verificationToken.trim(), expectedToken);
  }

  if (!requestIsAuthorized) {
    console.warn('Received request with invalid verification signature.');
    return {
      statusCode: 403,
      body: JSON.stringify({ message: 'Forbidden' }),
    };
  }

  let payload;
  try {
    payload = rawBody ? JSON.parse(rawBody) : {};
  } catch (error) {
    console.error('Failed to parse deletion payload.', error);
    return {
      statusCode: 400,
      body: JSON.stringify({ message: 'Invalid JSON payload' }),
    };
  }

  console.info('Marketplace account deletion payload received.', payload);

  const userId = resolveUserIdFromPayload(payload);
  if (!userId) {
    return jsonResponse(400, { message: 'Missing user identifier in payload' });
  }

  try {
    const deleted = await deleteUserById(userId);
    if (!deleted) {
      return jsonResponse(404, { message: 'Account not found' });
    }
  } catch (error) {
    console.error('Failed to delete marketplace account.', error);
    return jsonResponse(500, { message: 'Failed to delete account' });
  }

  console.info('Marketplace account deleted for', userId);

  return {
    statusCode: 204,
    body: '',
  };
};

exports.handler = handler;
module.exports = { handler };
