Feature: Create Community ID
  As a builder I want to create a community that I will be able to score passports for

  Scenario: Successfully create a Community ID
    Given that I have an API account
    When I hit the Add Community button
    And I enter a name for this Community that is unique among the Community registered under my account
    Then that Community is registered
    And that Community uses the latest weights and threshold
