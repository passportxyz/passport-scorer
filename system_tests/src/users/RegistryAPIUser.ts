import { BaseUser } from "./User";

export class RegistryAPIUser extends BaseUser {
  declare apiKey: string;
  declare scorerId: string;

  async init() {
    this.apiKey = process.env.TEST_SCORER_API_KEY!;
    this.scorerId = process.env.TEST_API_SCORER_ID!;
  }
}
