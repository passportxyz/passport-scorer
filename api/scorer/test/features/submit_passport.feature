Feature: Submit address for passport
  As a user of the passport scoring service
  I want to be able to submit eth addresses so I can get back 
  the score for the owner of that eth address

  # The "@" annotations are tags
  # One feature can have multiple scenarios
  # The lines immediately after the feature title are just comments

  Scenario: Submit passport successfully
    Given that I'm a Passport developer and have a community ID
    When I call the submit-passport API for an Ethereum account under that community ID
    Then the API reads all of the Passport data points
    Then the API logs all of the valid Passport data points (VCs), namely the complete JSON, mapped to that Passport holder within the respective community ID directory



  Scenario: As a developer, I want to rely on the Gitcoin Community Scorer scoring settings of the API
    Given that I have created a community ID
    Given I have not further configured its settings
    When I call the submit-passport API for an Ethereum account under that community ID
    Then I want to get a score based on the Gitcoin Community Score and deduplication rules (see default deduplication settings here)
    And log the score associated with this Passport under the corresponding community ID

