import { createActor, createMovie } from "../models.js";

const TOM_HANKS = createActor({ id: "Q1", displayText: "Tom Hanks" });
const HELEN_HUNT = createActor({ id: "Q2", displayText: "Helen Hunt" });
const BILL_PAXTON = createActor({ id: "Q3", displayText: "Bill Paxton" });
const EARLY_ONLY = createActor({
  id: "Q98",
  displayText: "Actor in an earlier movie only",
});
const OUTSIDER = createActor({ id: "Q99", displayText: "Unknown Actor" });

const CAST_AWAY = createMovie({
  id: "Q10",
  displayText: "Cast Away",
  castIds: ["Q1", "Q2"],
});
const TOY_STORY = createMovie({
  id: "Q20",
  displayText: "Toy Story",
  castIds: ["Q1"],
});
const UNRELATED = createMovie({
  id: "Q30",
  displayText: "Unrelated",
  castIds: ["Q1", "Q98"],
});
const EMPTY_CAST = createMovie({
  id: "Q40",
  displayText: "No Cast On Record",
  castIds: [],
});
const TWISTER = createMovie({
  id: "Q50",
  displayText: "twister",
  castIds: ["Q2", "Q3"],
});
const APOLLO = createMovie({
  id: "Q60",
  displayText: "Apollo 13",
  castIds: ["Q1", "Q3"],
});
