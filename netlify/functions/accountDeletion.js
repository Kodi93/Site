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
