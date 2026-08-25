import { describe, expect, it } from "vitest";
import {
  assertValidName,
  indexSource,
  packageJson,
  packageTsconfig,
  renderRootTsconfig,
  withReference,
} from "./newPackage.js";

describe("assertValidName", () => {
  it("accepts a kebab-case name", () => {
    expect(() => assertValidName("engine")).not.toThrow();
    expect(() => assertValidName("game-engine")).not.toThrow();
  });

  it("rejects empty, non-kebab, or scoped names", () => {
    expect(() => assertValidName("")).toThrow();
    expect(() => assertValidName("Engine")).toThrow();
    expect(() => assertValidName("game_engine")).toThrow();
    expect(() => assertValidName("@baconslaw/engine")).toThrow();
    expect(() => assertValidName("-engine")).toThrow();
  });
});

describe("packageJson", () => {
  it("mirrors the lib package shape under the scoped name", () => {
    const pkg = packageJson("engine");
    expect(pkg.name).toBe("@baconslaw/engine");
    expect(pkg.private).toBe(true);
    expect(pkg.type).toBe("module");
    expect(pkg.exports).toEqual({ ".": "./dist/index.js" });
    expect(pkg.scripts).toMatchObject({
      build: "tsc --build",
      typecheck: "tsc --build",
    });
    // Fresh package has no tests yet.
    const scripts = pkg.scripts as Record<string, string>;
    expect(scripts.test).toContain("--passWithNoTests");
    expect(pkg.devDependencies).toHaveProperty(
      "@baconslaw/tsconfig",
      "workspace:*",
    );
    expect(pkg.devDependencies).toHaveProperty("vitest");
  });
});

describe("packageTsconfig", () => {
  it("extends the node + lib presets with no references by default", () => {
    const cfg = packageTsconfig();
    expect(cfg.extends).toEqual([
      "@baconslaw/tsconfig/node",
      "@baconslaw/tsconfig/lib",
    ]);
    expect(cfg.compilerOptions).toMatchObject({
      rootDir: "src",
      outDir: "dist",
    });
    expect(cfg.include).toEqual(["src"]);
    expect(cfg.exclude).toEqual(["src/**/*.test.ts"]);
    expect(cfg).not.toHaveProperty("references");
  });

  it("wires workspace references when given dependency paths", () => {
    const cfg = packageTsconfig(["../lib"]);
    expect(cfg.references).toEqual([{ path: "../lib" }]);
  });
});

describe("indexSource", () => {
  it("is a non-empty barrel module", () => {
    expect(indexSource("engine")).toContain("export");
  });
});

describe("withReference", () => {
  const root = {
    files: [],
    references: [
      { path: "./packages/lib" },
      { path: "./packages/scripts" },
      { path: "./server" },
    ],
  };

  it("inserts a new reference sorted by path", () => {
    const next = withReference(root, "./packages/engine");
    expect(next.references).toEqual([
      { path: "./packages/engine" },
      { path: "./packages/lib" },
      { path: "./packages/scripts" },
      { path: "./server" },
    ]);
  });

  it("is idempotent when the reference already exists", () => {
    const next = withReference(root, "./packages/lib");
    expect(next.references).toEqual(root.references);
  });

  it("does not mutate the input", () => {
    withReference(root, "./packages/engine");
    expect(root.references).toHaveLength(3);
  });
});

describe("renderRootTsconfig", () => {
  it("renders reference objects on a single line, with a trailing newline", () => {
    const out = renderRootTsconfig({
      files: [],
      references: [{ path: "./packages/engine" }],
    });
    expect(out).toContain('{ "path": "./packages/engine" }');
    expect(out.endsWith("\n")).toBe(true);
  });
});
