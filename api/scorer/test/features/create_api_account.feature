Feature: Create an API account
  As a builder using the passport scoring service
  I want to be able to create an account
  where I can create API keys

  Scenario: Successfully create an API account
    Given that I am a builder and I don't have an API ACCOUNT
    When I hit the Connect Wallet button
    Then I Sign-in-with-Ethereum
    Then I will have an account created
    And be taken to the dashboard

  Scenario: Invalid Nonce useage
    Given that I have requested a nonce with the wrong address
    When I verify the SIWE message
    Then verification fails
