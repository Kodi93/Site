import type { Handler } from "@netlify/functions";
import { execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..");
const DATA_FILE = path.join(ROOT_DIR, "data", "products.json");
const DEFAULT_PY_ARGS = ["-m", "giftgrab.cli", "update"];

const parseProductsCount = async (): Promise<number> => {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf8");
    const payload = JSON.parse(raw);
    if (Array.isArray(payload?.products)) {
      return payload.products.length;
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      console.warn("Unable to parse product catalogue", error);
    }
  }
  return 0;
};

const triggerBuild = async (): Promise<boolean> => {
  const hook = process.env.NETLIFY_BUILD_HOOK ?? process.env.BUILD_HOOK_URL;
  if (!hook) {
    return false;
  }
  try {
    const response = await fetch(hook, { method: "POST" });
    if (!response.ok) {
      console.warn("Build hook returned non-2xx status", response.status);
    }
    return response.ok;
  } catch (error) {
    console.warn("Failed to trigger build hook", error);
    return false;
  }
};

const runRefreshCommand = async (): Promise<void> => {
  const pythonBinary = process.env.REFRESH_PYTHON_BINARY ?? "python";
  const args = process.env.REFRESH_COMMAND
    ? process.env.REFRESH_COMMAND.split(/\s+/).filter(Boolean)
    : DEFAULT_PY_ARGS;
  await execFileAsync(pythonBinary, args, {
    cwd: ROOT_DIR,
    env: {
      ...process.env,
      // Ensure the AFFIL_TAG flows through to the Python build for link hygiene.
      AFFIL_TAG: process.env.AFFIL_TAG ?? "kayce25-20",
    },
  });
};

export const handler: Handler = async () => {
  const startedAt = Date.now();
  try {
    await runRefreshCommand();
  } catch (error) {
    console.error("Catalogue refresh failed", error);
    return {
      statusCode: 500,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "Failed to refresh catalogue",
        error: error instanceof Error ? error.message : String(error),
      }),
    };
  }

  const refreshedCount = await parseProductsCount();
  const buildTriggered = await triggerBuild();

  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      refreshed: refreshedCount,
      buildTriggered,
      durationMs: Date.now() - startedAt,
    }),
  };
};

export default handler;
