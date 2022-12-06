import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";



Given("that I am a builder", () => {
  cy.visit("http://localhost:3000/");
});

Given("I don't have an API ACCOUNT", () => {
  cy.siwe();
});

When("I hit create account", ()=> {
  cy.get('button').contains('Connect Wallet').click();
});

When("I Sign-in-with-Ethereum", () => {});

Then("I will have an account created", () => {});
Then("be taken to the config dashboard", () => {});


