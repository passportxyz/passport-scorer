Feature: Create Community ID (#693)
  Scenario: Successfully create a Community ID
    Given that I have an API account
    When I hit the Add Community button
    Then I enter a name for this Community that is unique among the Community registered under my account
    Then that Community is registered
