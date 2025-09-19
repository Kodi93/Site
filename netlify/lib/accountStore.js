const fs = require('fs/promises');
const path = require('path');

const DATA_PATH = process.env.ACCOUNT_STORE_DATA_PATH;

function normalizeIdentifier(value) {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

async function deleteUserById(userId) {
  const normalized = normalizeIdentifier(userId);
  if (!normalized) {
    throw new Error('A valid user ID is required to delete an account.');
  }

  console.info('Deleting marketplace account for', normalized);

  if (!DATA_PATH) {
    return true;
  }

  const storePath = path.resolve(DATA_PATH);
  let payload;
  try {
    const raw = await fs.readFile(storePath, 'utf8');
    payload = raw ? JSON.parse(raw) : {};
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return false;
    }
    throw error;
  }

  if (!payload || typeof payload !== 'object') {
    return false;
  }

  const users = Array.isArray(payload.users) ? payload.users : [];
  let removed = false;
  const filtered = users.filter((entry) => {
    if (!entry || typeof entry !== 'object') {
      return true;
    }
    const identifiers = [
      entry.id,
      entry.userId,
      entry.user_id,
      entry.accountId,
      entry.account_id,
    ];
    if (identifiers.some((candidate) => normalizeIdentifier(candidate) === normalized)) {
      removed = true;
      return false;
    }
    return true;
  });

  if (!removed) {
    return false;
  }

  const nextPayload = { ...payload, users: filtered };
  await fs.writeFile(storePath, JSON.stringify(nextPayload, null, 2), 'utf8');
  return true;
}

module.exports = { deleteUserById };
