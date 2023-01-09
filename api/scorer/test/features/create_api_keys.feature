Feature: Create API keys
  As a builder I want to create API keys that will allow my apps to interact with the Gitcoin Passport API

  Scenario: Successfully create API keys for my apps
    Given that I have an API account
    When I hit the Create API key button
    Then I’m returned a secret API key, basically a long cryptic string
    And I can use that key to call the API
