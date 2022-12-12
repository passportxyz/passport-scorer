Feature: API Account (#689)
  Scenario: Create new API Account
    Given that I am a builder
    And I don't have an API ACCOUNT
    When I hit create account
    And I Sign-in-with-Ethereum
    Then I will have an account created
    And be taken to the config dashboard
