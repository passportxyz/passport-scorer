import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";

Given("that I am a builder", () => {
});

Given("I don't have an API ACCOUNT", () => {
  cy.siwe();
});

When("I hit create account", () => {
  cy.visit("");
  cy.get("button").contains("Sign-in with Ethereum").click();
});

When("I Sign-in-with-Ethereum", () => {});

Then("I will have an account created", () => {});
Then("be taken to the config dashboard", () => {
  cy.visit("/dashboard");
});
