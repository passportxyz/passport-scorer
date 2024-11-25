import { stack } from "./config";

export const defaultTags = {
  Application: "ops",
  Repo: "https://github.com/passportxyz/core-infra",
  PulumiStack: stack,
  Environment: stack,
  ManagedBy: "pulumi",
  Name: "missing",
};
