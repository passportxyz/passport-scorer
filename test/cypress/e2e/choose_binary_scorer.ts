import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";
import "../support/commands";

Given("that I'm a developer and have setup a community", () => {
  cy.visit("http://localhost:3000/");
  cy.siwe();
});

When("I see the scoring options I can select for that community", () => {
  cy.get("button").contains("Communities").click();
});

Then(
  "I see the Gitcoin Binary Community Score as an option, i.e., the binary output version of the of the default Gitcoin Community Score",
  () => {}
);
