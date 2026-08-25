import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

// Scaffolds a new `@baconslaw/<name>` workspace package modeled on `packages/lib`
// and wires it into the root `ts/tsconfig.json` project references.
//
// Run: pnpm --filter @baconslaw/scripts new-package <name>

const SCOPE = "@baconslaw";
const NAME_RE = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;

type Json = Record<string, unknown>;

interface RootTsconfig {
  files: unknown[];
  references: { path: string }[];
  [key: string]: unknown;
}

export function assertValidName(name: string): void {
  if (!NAME_RE.test(name)) {
    throw new Error(
      `Invalid package name "${name}": use lowercase kebab-case (e.g. "engine"), unscoped.`,
    );
  }
}

export function packageJson(name: string): Json {
  return {
    $schema: "https://json.schemastore.org/package.json",
    name: `${SCOPE}/${name}`,
    private: true,
    version: "0.0.0",
    type: "module",
    exports: {
      ".": "./dist/index.js",
    },
    scripts: {
      dev: "tsc --build --watch",
      build: "tsc --build",
      typecheck: "tsc --build",
      clean: "rm -rf dist *.tsbuildinfo",
      test: "vitest run --passWithNoTests",
      "test:watch": "vitest --passWithNoTests",
    },
    devDependencies: {
      "@baconslaw/tsconfig": "workspace:*",
      "@types/node": "^24.0.0",
      typescript: "^7.0.0",
      vitest: "^4.1.11",
    },
  };
}

export function packageTsconfig(references: string[] = []): Json {
  const cfg: Json = {
    $schema: "https://json.schemastore.org/tsconfig",
    extends: ["@baconslaw/tsconfig/node", "@baconslaw/tsconfig/lib"],
    compilerOptions: {
      rootDir: "src",
      outDir: "dist",
    },
    include: ["src"],
    exclude: ["src/**/*.test.ts"],
  };
  if (references.length > 0) {
    cfg.references = references.map((path) => ({ path }));
  }
  return cfg;
}

export function indexSource(name: string): string {
  return `// Public API for ${SCOPE}/${name}. Re-export the package's modules here.\nexport {};\n`;
}

export function withReference(root: RootTsconfig, path: string): RootTsconfig {
  const references = root.references ?? [];
  if (references.some((ref) => ref.path === path)) {
    return root;
  }
  const merged = [...references, { path }].sort((a, b) =>
    a.path.localeCompare(b.path),
  );
  return { ...root, references: merged };
}

export function renderRootTsconfig(root: RootTsconfig): string {
  const json = JSON.stringify(root, null, 2);
  // Collapse each `{ "path": "..." }` reference onto a single line
  const collapsed = json.replace(
    /\{\s*"path":\s*("[^"]*")\s*\}/g,
    '{ "path": $1 }',
  );
  return `${collapsed}\n`;
}

function toJsonFile(value: Json): string {
  return `${JSON.stringify(value, null, 2)}\n`;
}

// Pass generated files through Biome to match the sibling packages and satisfy `pnpm lint`.
async function formatWithBiome(paths: string[]): Promise<void> {
  if (paths.length === 0) {
    return;
  }
  await execFileAsync("pnpm", ["exec", "biome", "format", "--write", ...paths]);
}

interface Paths {
  packagesDir: string;
  rootTsconfig: string;
}

function resolvePaths(scriptDir: string): Paths {
  // scriptDir === ts/packages/scripts/src
  return {
    packagesDir: resolve(scriptDir, "../.."),
    rootTsconfig: resolve(scriptDir, "../../..", "tsconfig.json"),
  };
}

export async function scaffold(
  name: string,
  references: string[],
  paths: Paths,
): Promise<string[]> {
  assertValidName(name);

  const targetDir = join(paths.packagesDir, name);
  const srcDir = join(targetDir, "src");
  const pkgFile = join(targetDir, "package.json");

  if (existsSync(pkgFile)) {
    throw new Error(`Package already exists: ${targetDir}`);
  }

  await mkdir(srcDir, { recursive: true });

  const written: string[] = [];
  const write = async (file: string, contents: string) => {
    await mkdir(dirname(file), { recursive: true });
    await writeFile(file, contents);
    written.push(file);
  };

  await write(pkgFile, toJsonFile(packageJson(name)));
  await write(
    join(targetDir, "tsconfig.json"),
    toJsonFile(packageTsconfig(references)),
  );
  await write(join(srcDir, "index.ts"), indexSource(name));

  const rootText = await readFile(paths.rootTsconfig, "utf8");
  const root = JSON.parse(rootText) as RootTsconfig;
  const nextRoot = withReference(root, `./packages/${name}`);
  if (nextRoot !== root) {
    await writeFile(paths.rootTsconfig, renderRootTsconfig(nextRoot));
    written.push(paths.rootTsconfig);
  }

  await formatWithBiome(written);

  return written;
}

async function main(): Promise<void> {
  const [name, ...rest] = process.argv.slice(2);
  if (!name) {
    console.error(
      "Usage: pnpm --filter @baconslaw/scripts new-package <name> [--ref ../lib ...]",
    );
    process.exitCode = 1;
    return;
  }

  const references: string[] = [];
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === "--ref" && rest[i + 1]) {
      references.push(rest[++i] as string);
    }
  }

  const paths = resolvePaths(import.meta.dirname);
  const written = await scaffold(name, references, paths);

  console.log(`Scaffolded ${SCOPE}/${name}:`);
  for (const file of written) {
    console.log(`  ${file}`);
  }
  console.log("\nNext:");
  console.log("  pnpm install            # link the new workspace package");
  console.log(
    `  # add "${SCOPE}/${name}": "workspace:*" to any consumer, plus a tsconfig reference`,
  );
}

// Run main only when executed directly, not when imported by tests.
if (import.meta.filename === process.argv[1]) {
  await main();
}
