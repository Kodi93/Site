const crypto = require('crypto');
const { URL, URLSearchParams } = require('url');

const REQUIRED_METHOD = 'POST';
const EXPECTED_TOKEN = 'gdel1f4f2f7c9b0a4f2e86b0bb7fb6c0f1a5';
const HEALTH_CHECK_METHODS = new Set(['GET', 'HEAD']);

const CHALLENGE_PARAM_KEYS = ['challenge_code', 'challengeCode'];

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

  const headers = event.headers || {};
  const host = headers.host || headers.Host;
  const path = event.path || '';
  if (!host) {
    return path;
  }

  const protocol =
    headers['x-forwarded-proto'] ||
    headers['X-Forwarded-Proto'] ||
    headers['x-forwarded_proto'] ||
    'https';
  return `${protocol}://${host}${path}`;
}

exports.handler = async (event) => {
  const method = event.httpMethod || '';
  const headers = event.headers || {};

  if (method === 'GET') {
    const challengeCode = extractChallengeCode(event);
    if (challengeCode) {
      const endpoint = resolveEndpoint(event);
      const hash = crypto.createHash('sha256');
      hash.update(challengeCode);
      hash.update(EXPECTED_TOKEN);
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

  const receivedToken =
    headers['x-verification-token'] ||
    headers['X-Verification-Token'] ||
    headers['x-verificationtoken'] ||
    headers['x-verification_token'];

  if (receivedToken !== EXPECTED_TOKEN) {
    console.warn('Received request with invalid verification token.');
    return {
      statusCode: 403,
      body: JSON.stringify({ message: 'Forbidden' }),
    };
  }

  let rawBody = event.body || '';
  if (event.isBase64Encoded) {
    rawBody = Buffer.from(rawBody, 'base64').toString('utf8');
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

  // TODO: Wire up your persistence layer deletion logic here.
  // Example: await deleteUserById(payload.userId);

  return {
    statusCode: 204,
    body: '',
  };
};
