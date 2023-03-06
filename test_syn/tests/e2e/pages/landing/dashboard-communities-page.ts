import { Page } from "../page";

export default class DashboardCommunities extends Page {
  constructor() {
    super();
  }

  visit() {
    cy.visit("/dashboard/scorer");

    // Check that the *highlighted* tab is visible
    cy.get('button[data-testid="scorer-tab"].text-blue-darkblue').should("be.visible");
  }
}
