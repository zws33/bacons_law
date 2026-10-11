import { ValidationError } from "./errors.js";

export type EntityId = string;

export type Actor = {
  readonly kind: "actor";
  readonly id: EntityId;
  readonly displayText: string;
  readonly imagePath: string | null;
};

export type Movie = {
  readonly kind: "movie";
  readonly id: EntityId;
  readonly displayText: string;
  readonly castIds: ReadonlySet<EntityId>; // the validation contract (R12)
  readonly imagePath: string | null;
  readonly releaseYear: string | null;
};

export type Move = Actor | Movie;

type ActorInput = {
  id: EntityId;
  displayText: string;
  imagePath?: string | null;
};

type MovieInput = {
  id: EntityId;
  displayText: string;
  castIds: Iterable<EntityId>;
  imagePath?: string | null;
  releaseYear?: string | null;
};

const requireId = (id: EntityId, label: string): EntityId => {
  if (id.trim() === "") {
    throw new ValidationError(
      `${label} must be a non-blank id, got ${JSON.stringify(id)}`,
    );
  }
  return id;
};

export const createActor = (input: ActorInput): Actor => {
  return {
    kind: "actor",
    id: requireId(input.id, "Actor.id"),
    displayText: input.displayText,
    imagePath: input.imagePath ?? null,
  };
};

export const createMovie = (input: MovieInput): Movie => {
  return {
    kind: "movie",
    id: requireId(input.id, "Movie.id"),
    displayText: input.displayText,
    // An empty castIds is legal data (R13); a blank *member* is not.
    castIds: new Set(
      [...input.castIds].map((id) => requireId(id, "Movie.castIds member")),
    ),
    imagePath: input.imagePath ?? null,
    releaseYear: input.releaseYear ?? null,
  };
};
