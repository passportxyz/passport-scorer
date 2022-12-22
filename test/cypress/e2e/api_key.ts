import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";

Given("that I have an API account", () => {
  cy.siwe();
  cy.visit("http://localhost:3000/");
  cy.get("button").contains("Connect Wallet").click();
  cy.visit("http://localhost:3000/dashboard");
});

When("I hit to create an API key", () => {
  cy
    .get("[data-testid='api-keys-tab']")
    .contains("API Keys")
    .click();
  cy.get("button").contains("Add").click();
  cy.get("[data-testid='key-name-input']").type("test");
  cy.get("[data-testid='create-button']").click();
});

Then("I’m returned a secret API key, basically a long cryptic string", () => {

});

Then("I can use that key to call the API", () => {});
