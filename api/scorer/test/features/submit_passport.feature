Feature: Submit address for passport
  As a user of the passport scoring service
  I want to be able to submit eth addresses so I can get back
  the score for the owner of that eth address

  Scenario: Submit passport successfully
    Given that I'm a Passport developer and have a community ID
    When I call the `/registry/submit-passport` API for an Ethereum account and a community ID
    Then I receive back the score details with status `PROCESSING`

  Scenario: Scoring is in progress
    Given that I'm a Passport developer and have a community ID
    And that I have submitted a passport for scoring using the api
    And And the scoring of the passport is still in progress
    When I call the `/registry/score` API for an Ethereum account and a community ID
    Then I receive back the score details with status `PROCESSING` while the scoring is still in progress

  Scenario: Scoring failed
    Given that I'm a Passport developer and have a community ID
    And that I have submitted a passport for scoring using the api
    And the scoring of the passport has failed
    When I call the `/registry/score` API for an Ethereum account and a community ID
    Then I receive back the score details with status `ERROR`

  Scenario: Scoring succeeded
    Given that I'm a Passport developer and have a community ID
    And that I have submitted a passport for scoring using the api
    And the scoring of the passport has finished successfully
    When I call the `/registry/score` API for an Ethereum account and a community ID
    Then I receive back the score details with status `DONE`

  Scenario: Reset error if scoring succeeded after an initial error
    Given that I'm a Passport developer and have a community ID
    And that I have submitted a passport for scoring using the api
    And the scoring of the passport has failed
    And I have submitted the passport for scoring a second time
    And the scoring of the passport has finished successfully
    When I call the `/registry/score` API for an Ethereum account and a community ID
    Then I receive back the score details with status `DONE`
    And the previous error message has been reset to None

  Scenario: As a developer, I want to rely on the Gitcoin Community Scorer scoring settings of the API
    Given that I have created a community ID
    And I have not further configured its settings
    And that I have submitted a passport for scoring using the api
    And the scoring of the passport has finished successfully
    When I call the `/registry/score` API for an Ethereum account and a community ID
    Then I want to get a score based on the Gitcoin Community Score and deduplication rules (see default deduplication settings here)
