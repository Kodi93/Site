<<<< codex/create-account-deletion-netlify-function-uz8ih4
export async function handler(event) {
  const headers = event.headers || {};
  const token =
    headers['x-verification-token'] ||
    headers['x-verificationtoken'] ||
    headers['x-verification_token'];

  if (token !== process.env.DELETION_TOKEN) {
    return { statusCode: 403, body: 'Invalid token' };
  }

  let body = {};
  try {
    body = JSON.parse(event.body || '{}');
  } catch (error) {
    console.warn('Failed to parse deletion payload:', error);
  }

  // TODO: delete user data in your DB using body.userId / body.email
  console.log('Marketplace delete request:', body);

  return { statusCode: 200, body: 'ok' };
}
====
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
>>>> main
