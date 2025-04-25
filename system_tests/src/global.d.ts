import { CancelTokenSource } from "axios";

interface CustomMatchers<R = unknown> {
  toHaveStatus(expectedCode: number): R;
}

declare global {
  namespace jest {
    interface Expect extends CustomMatchers {}
    interface Matchers<R> extends CustomMatchers<R> {}
    interface InverseAsymmetricMatchers extends CustomMatchers {}
  }

  var axiosCancelTokens: CancelTokenSource[] | undefined;
}

export {};
