import { AuthStrategy, TestRequestOptionsNoAuth } from "../../types";

type AuthStrategyOptions = {
  name: string;
};

export abstract class BaseAuthStrategy implements AuthStrategy {
  name: string;

  constructor({ name }: AuthStrategyOptions) {
    // To be used for e.g. creating an index of endpoints including info about auth strategies
    this.name = name;
  }

  // Accepts options and returns modified options with authentication added
  // (i.e. adding a simple key to a header, or doing several complex requests to generate a token)
  abstract applyAuth(options: TestRequestOptionsNoAuth): Promise<TestRequestOptionsNoAuth>;
}
