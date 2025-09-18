const REQUIRED_METHOD = 'POST';

exports.handler = async (event) => {
  if (event.httpMethod !== REQUIRED_METHOD) {
    return {
      statusCode: 405,
      headers: {
        Allow: REQUIRED_METHOD,
      },
      body: JSON.stringify({ message: 'Method Not Allowed' }),
    };
  }

  const expectedToken = process.env.MARKETPLACE_DELETION_TOKEN;

  if (!expectedToken) {
    console.error('MARKETPLACE_DELETION_TOKEN is not configured.');
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'Server misconfiguration.' }),
    };
  }

  const headers = event.headers || {};
  const receivedToken = headers['x-verification-token'] || headers['X-Verification-Token'];

  if (!receivedToken || receivedToken !== expectedToken) {
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
