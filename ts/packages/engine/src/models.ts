export type EntityId = string;

export type Actor = {
  readonly id: EntityId;
  readonly displayText: string;
  readonly imagePath: string | null;
};

export type Movie = {
  readonly id: EntityId;
  readonly displayText: string;
  readonly castIds: ReadonlySet<EntityId>;
  readonly imagePath: string | null;
  readonly releaseYear: string | null;
};
type ActorInput = Pick<Actor, "id" | "displayText"> & {
  imagePath?: string | null;
};

type MovieInput = Pick<Movie, "id" | "displayText"> & {
  castIds: Iterable<EntityId>;
  imagePath?: string | null;
  releaseYear?: string | null;
};

export const createActor = (input: ActorInput): Actor => {
  return {
    ...input,
    imagePath: input.imagePath ?? null,
  };
};

export const createMovie = (input: MovieInput): Movie => {
  return {
    ...input,
    castIds: input.castIds ? new Set(input.castIds) : new Set(),
    imagePath: input.imagePath ?? null,
    releaseYear: input.releaseYear ?? null,
  };
};

const RoundEndReason = {
  Unconnected: "unconnected",
  Repeat: "repeat",
  GaveUp: "gaveUp",
  DeadlineLapsed: "deadlineLapsed",
};

type RoundEndReason = (typeof RoundEndReason)[keyof typeof RoundEndReason];
