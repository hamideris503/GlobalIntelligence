/** Minimal ambient declarations for the Node builtins the E2E specs import.
 *
 * This repo ships no `@types/node` (and does not typecheck `apps/web/e2e` in
 * its tsc program, which only includes `src`), so specs get their two builtins
 * from here instead of adding a dependency. Keep this file free of
 * imports/exports: it must stay a script so the declarations are ambient.
 */

declare module "node:fs" {
  export function existsSync(path: string): boolean;
  export function readFileSync(path: string, encoding: "utf-8"): string;
}

declare module "node:url" {
  export function fileURLToPath(url: URL | string): string;
}
