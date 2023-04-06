import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";

Given("that I have an API account", () => {
  cy.siwe();
  cy.visit("/#/dashboard/scorer");
});

When("I hit to create an API key", () => {
  cy.get('#tabSelect')
    .select('api-keys', { force: true });
  cy.get("button[data-testid='no-values-add']").contains("API Key").click();
  cy.get("[data-testid='key-name-input']").type("testing");
  cy.get("button").contains("Create").click();
});

Then("I’m returned a secret API key, basically a long cryptic string", () => {
  cy.get("button[data-testid='copy-api-key']");
});

Then("I can use that key to call the API", () => {});
