
Feature: API Account (#692)
  Scenario: Create new API Account
    Given that I have an API account
    When I hit to create an API key
    Then I’m returned a secret API key, basically a long cryptic string
    And I can use that key to call the API
