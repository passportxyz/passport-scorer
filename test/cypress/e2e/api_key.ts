import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";

Given("that I have an API account", () => {
  cy.siwe();
  cy.visit("http://localhost:3000/");
});

When("I hit to create an API key", () => {
    
});

Then(
  "I’m returned a secret API key, basically a long cryptic string",
  () => {}
);

Then("I can use that key to call the API", () => {});
