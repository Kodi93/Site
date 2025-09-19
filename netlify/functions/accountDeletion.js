exports.handler = async (event) => {
  const header = event.headers?.["x-verification-token"] || event.headers?.["X-Verification-Token"];
  const expected = process.env.ACCOUNT_DELETION_TOKEN;
  if (!expected) return { statusCode: 500, body: "Missing env" };
  if (header !== expected) return { statusCode: 401, body: "Unauthorized" };
  return { statusCode: 204, body: "" };
};
