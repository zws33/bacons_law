#! /usr/bin/env node
import { once } from "node:events";
import { createReadStream, createWriteStream, existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { createInterface } from "node:readline";
import type { Writable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { parseArgs } from "node:util";
import { makeSearchKey } from "@baconslaw/lib";
import { stringify } from "csv-stringify";

export interface Edge {
  movie: string;
  movie_label: string;
  movie_sitelinks: number;
  movie_year: number;
  actor: string;
  actor_label: string;
  actor_sitelinks: number;
}

async function main() {
  const args = parseArgs({
    options: {
      limit: { type: "string", short: "l" },
      inputPath: { type: "string", short: "i" },
      outputDir: { type: "string", short: "o" },
    },
    allowPositionals: true,
  }).values;

  const limit = Number.parseInt(args.limit ?? "", 10);
  const inputPath = args.inputPath;
  const outputDir = args.outputDir;

  if (limit && Number.isNaN(limit)) {
    throw new Error("--limit must be a number");
  }

  if (!inputPath) {
    throw new Error("--inputPath is required");
  }

  if (!outputDir) {
    throw new Error("--outputDir is required");
  }

  if (!existsSync(inputPath)) {
    throw new Error(`Input file does not exist: ${inputPath}`);
  }

  const actorsOutput = resolve(outputDir, "actors.csv");
  const moviesOutput = resolve(outputDir, "movies.csv");
  const edgesOutput = resolve(outputDir, "edges.csv");

  await mkdir(outputDir, { recursive: true });

  const inputStream = createInterface({
    input: createReadStream(inputPath, "utf8"),
  });

  const actorsFile = createWriteStream(actorsOutput, { encoding: "utf8" });
  const moviesFile = createWriteStream(moviesOutput, { encoding: "utf8" });
  const edgesFile = createWriteStream(edgesOutput, { encoding: "utf8" });

  const actorsTransform = stringify({
    header: true,
    columns: ["actor_id", "actor_label", "actor_sitelinks", "actor_search_key"],
  });

  const moviesTransform = stringify({
    header: true,
    columns: [
      "movie_id",
      "movie_label",
      "movie_sitelinks",
      "movie_year",
      "movie_search_key",
    ],
  });

  const edgesTransform = stringify({
    header: true,
    columns: ["movie_id", "actor_id"],
  });

  const pipelines = [
    pipeline(actorsTransform, actorsFile),
    pipeline(moviesTransform, moviesFile),
    pipeline(edgesTransform, edgesFile),
  ];

  const actorsSeen = new Set<string>();
  const moviesSeen = new Set<string>();
  let edgesCount = 0;
  let lineNumber = 0;

  for await (const line of inputStream) {
    lineNumber++;

    if (limit && lineNumber > limit) {
      break;
    }

    if (!line.trim()) continue;

    let edge: Edge;

    try {
      edge = JSON.parse(line) as Edge;
    } catch (err) {
      throw new Error(`Error decoding JSON on line ${lineNumber}`, {
        cause: err,
      });
    }

    if (!actorsSeen.has(edge.actor)) {
      const actorRow = {
        actor_id: edge.actor,
        actor_label: edge.actor_label,
        actor_sitelinks: edge.actor_sitelinks,
        actor_search_key: searchKeyFor(edge.actor_label, edge, lineNumber),
      };
      await safeWrite(actorsTransform, actorRow);
      actorsSeen.add(edge.actor);
    }

    if (!moviesSeen.has(edge.movie)) {
      const movieRow = {
        movie_id: edge.movie,
        movie_label: edge.movie_label,
        movie_sitelinks: edge.movie_sitelinks,
        movie_year: edge.movie_year,
        movie_search_key: searchKeyFor(edge.movie_label, edge, lineNumber),
      };
      await safeWrite(moviesTransform, movieRow);
      moviesSeen.add(edge.movie);
    }

    const edgeRow = {
      movie_id: edge.movie,
      actor_id: edge.actor,
    };
    await safeWrite(edgesTransform, edgeRow);
    edgesCount++;
  }

  actorsTransform.end();
  moviesTransform.end();
  edgesTransform.end();

  await Promise.all(pipelines);

  console.table({
    movies: moviesSeen.size,
    actors: actorsSeen.size,
    edges: edgesCount,
  });
}

function searchKeyFor(label: string, edge: Edge, lineNumber: number): string {
  try {
    return makeSearchKey(label);
  } catch (err) {
    throw new Error(
      `Failed to transform edge ${JSON.stringify(edge)}, line number: ${lineNumber}`,
      { cause: err },
    );
  }
}

async function safeWrite<Row extends object>(stream: Writable, data: Row) {
  if (!stream.write(data)) {
    await once(stream, "drain");
  }
}
main().catch((err) => {
  console.error(err);
  process.exit(1);
});
