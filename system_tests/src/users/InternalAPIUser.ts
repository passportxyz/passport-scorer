import { BaseUser } from "./User";

export class InternalAPIUser extends BaseUser {
  declare apiSecret: string;
  declare scorerId: string;

  async init() {
    this.apiSecret = process.env.TEST_INTERNAL_API_SECRET!;
    this.scorerId = process.env.TEST_UI_SCORER_ID!;
  }
}
