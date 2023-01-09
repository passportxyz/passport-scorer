import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";

Given("that I'm a developer and have setup a community", () => {
  cy.siwe();
  cy.visit("http://localhost:3000/");
  cy.get("button").contains("Connect Wallet").click();
  cy.visit("http://localhost:3000/dashboard");
  cy.get("button").contains("Add").click();
  cy.get('[data-testid="community-name-input"]').type("Test Community");
  cy.get('[data-testid="community-description-input"]').type(
    "Test Description"
  );
  cy.get('[data-testid="create-button"]').click();
  cy.get("a").contains("Test Community").click();
});

When("I see the scoring options I can select for that community", () => {
});

Then(
  "I see the Gitcoin Binary Community Score as an option, i.e., the binary output version of the of the default Gitcoin Community Score",
  () => {
    cy.get("p").contains("Weighted Binary");
  }
);
