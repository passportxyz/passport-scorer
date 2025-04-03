import { TestRequestOptionsNoAuth } from "../../types";
import { BaseAuthStrategy } from "./strategy";

interface HeaderKeyAuthConfig {
  key: string;
  header?: string;
}

export class HeaderKeyAuth extends BaseAuthStrategy {
  key: string;
  header: string;

  constructor({ key, header }: HeaderKeyAuthConfig) {
    super({ name: "header-key-auth" });
    this.key = key;
    this.header = header || "Authorization";
  }

  async applyAuth(options: TestRequestOptionsNoAuth): Promise<TestRequestOptionsNoAuth> {
    return {
      ...options,
      headers: {
        ...options.headers,
        [this.header]: this.key,
      },
    };
  }
}
