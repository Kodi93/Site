const REQUIRED_METHOD = 'POST';
const EXPECTED_TOKEN = 'gdel1f4f2f7c9b0a4f2e86b0bb7fb6c0f1a5';
const HEALTH_CHECK_METHODS = new Set(['GET', 'HEAD']);

exports.handler = async (event) => {
  const method = event.httpMethod || '';

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

  const headers = event.headers || {};
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
