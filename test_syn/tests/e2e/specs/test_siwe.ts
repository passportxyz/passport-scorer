/* eslint-disable ui-testing/missing-assertion-in-test */
import LandingPage from "../pages/landing/landing-page";

const landing = new LandingPage();

describe("Connect", () => {
  it("passes", () => {
    landing.visit();
    landing.signInWithEthereum();
    landing.waitUntilSignedIn();
  });
});
