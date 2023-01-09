import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";


Given("that I have an API account", () => {
  cy.siwe();
  cy.visit("http://localhost:3000/");
  cy.get("button").contains("Connect Wallet").click();
  cy.visit("http://localhost:3000/dashboard");
});


When("I hit the Add Community button", () => {
  cy.get("button").contains("Add").click();
});

Then("I enter a name for this Community that is unique among the Community registered under my account", () => {
  cy.get("[data-testid='community-name-input']").type("test");
  cy.get("[data-testid='community-description-input']").type(
    "test"
    );
    cy.get("[data-testid='create-button']").click();
  });

  Then("that Community is registered", () => {
  });
