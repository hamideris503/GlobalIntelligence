/** Loopback port resolution for the local E2E suites.
 *
 * Test ports must be overridable: on Windows, Docker Desktop / Hyper-V reserve
 * whole blocks of TCP ports. A reserved port does not answer "address in use" —
 * the OS refuses the bind with `EACCES`, which surfaces as an opaque
 * `listen EACCES: permission denied 127.0.0.1:<port>` from the web server.
 *
 * `resolveLoopbackPort` reads `envVar` (falling back to the historical default
 * so CI and previous local runs are unaffected), probes 127.0.0.1, and fails
 * loudly with an actionable hint instead of that cryptic error.
 *
 * The probe runs in a child process on purpose: a Playwright config must export
 * a plain object (this version rejects function/async exports) while
 * `net.Server.listen` is asynchronous-only, so it cannot be awaited in-place.
 */
import { execFileSync } from "node:child_process";

const PROBE = [
  'const net = require("node:net");',
  "const s = net.createServer();",
  's.once("error", (e) => { process.stdout.write(String(e.code || "ERR")); s.close(() => {}); });',
  's.once("listening", () => { process.stdout.write("OK"); s.close(() => {}); });',
  's.listen(Number(process.argv[1]), "127.0.0.1");',
].join("\n");

function probePort(port: number): string {
  try {
    return execFileSync(process.execPath, ["-e", PROBE, String(port)], {
      encoding: "utf8",
    }).trim();
  } catch {
    return "ERR";
  }
}

/** A loopback port that is free right now, or a clear error explaining how to change it. */
export function resolveLoopbackPort(envVar: string, defaultPort: number): number {
  const raw = process.env[envVar]?.trim();
  const port = raw ? Number(raw) : defaultPort;
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`[e2e] ${envVar}=${JSON.stringify(raw)} is not a valid TCP port (1-65535).`);
  }
  // Workers re-load this config *after* Playwright started the web server on the
  // same port, so probing there would always report EADDRINUSE. Probe once, in
  // the main process; workers only need the resolved number.
  if (process.env.TEST_WORKER_INDEX !== undefined) return port;

  const status = probePort(port);
  if (status === "OK") return port;

  const reason =
    status === "EACCES"
      ? "the OS forbids the bind (on Windows, Docker Desktop/Hyper-V reserve blocks of ports)"
      : status === "EADDRINUSE"
        ? "another process is already listening on it"
        : `bind failed (${status})`;
  const suggestion = defaultPort + 10000;
  throw new Error(
    `[e2e] unusable test port 127.0.0.1:${port}: ${reason}.\n` +
      `[e2e] pick a free loopback port and set ${envVar}, e.g.\n` +
      `[e2e]   PowerShell:  $env:${envVar}=${suggestion}; npm run test:e2e:fullstack\n` +
      `[e2e]   bash/CI:     ${envVar}=${suggestion} npm run test:e2e:fullstack`,
  );
}
