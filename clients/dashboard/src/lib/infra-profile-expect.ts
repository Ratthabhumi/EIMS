import { readFileSync, existsSync } from "fs";
import { join } from "path";

/**
 * Whether optional compose profiles are expected to be running.
 * Scripts write deployments/local/active-profiles.env; env vars override the file.
 */
export type ProfileExpect = {
  observability: boolean;
  pooler: boolean;
};

function parseBool(raw: string | undefined, fallback: boolean): boolean {
  if (raw === undefined || raw === "") return fallback;
  const v = raw.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(v)) return true;
  if (["0", "false", "no", "off"].includes(v)) return false;
  return fallback;
}

function readProfilesFile(): Record<string, string> {
  const candidates = [
    join(process.cwd(), "deployments", "local", "active-profiles.env"),
    join(process.cwd(), "..", "..", "deployments", "local", "active-profiles.env"),
    join(process.cwd(), "..", "deployments", "local", "active-profiles.env"),
  ];
  for (const path of candidates) {
    if (!existsSync(path)) continue;
    const out: Record<string, string> = {};
    for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eq = trimmed.indexOf("=");
      if (eq <= 0) continue;
      out[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
    }
    return out;
  }
  return {};
}

export function readProfileExpect(): ProfileExpect {
  const file = readProfilesFile();
  return {
    observability: parseBool(
      process.env.EIMS_EXPECT_OBSERVABILITY ?? file.EIMS_EXPECT_OBSERVABILITY,
      false,
    ),
    pooler: parseBool(process.env.EIMS_EXPECT_POOLER ?? file.EIMS_EXPECT_POOLER, false),
  };
}
