import { Page } from "../page";

export default class DashboardCommunities extends Page {
  constructor() {
    super();
  }

  visit() {
    cy.visit("/dashboard/community");

    // Check that the *highlighted* tab is visible
    cy.get('button[data-testid="communities-tab"].font-bold.font-blue-darkblue').should("be.visible");
  }
}
