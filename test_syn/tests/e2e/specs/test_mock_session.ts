/* eslint-disable ui-testing/missing-assertion-in-test */
import DashboardCommunities from "../pages/landing/dashboard-communities-page";

const dashboardCommunities = new DashboardCommunities();

describe("Connect", () => {
  it("passes", () => {
    cy.createScorerSession();
    dashboardCommunities.visit();
  });
});
