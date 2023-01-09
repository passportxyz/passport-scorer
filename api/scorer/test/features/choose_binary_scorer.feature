Feature: Select Binary Scorer
  As a user

  Scenario: As a developer, I want to choose the Gitcoin Binary Community Score
    Given that I select the Gitcoin Binary Community Score as an option
    When the selection takes effect
    Then it automatically becomes the new rule in the respective community

    When I choose to score a passport
    Then the binary score should be returned
    And the raw score should be returned
    And the threshold should be returned

  Scenario: Get score of "0.000000000"
    When I submit a passport that yields a weighted score less than the threshold
    Then the score "0.000000000" is returned

  Scenario: Get score of "1.000000000"
    When I submit a passport that yields a weighted score greater or equal than the threshold
    Then the score "1.000000000" is returned
