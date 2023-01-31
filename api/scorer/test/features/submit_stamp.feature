Feature: Claim of Stamps in Scorer database via API call
  As a Passport holder, I want to claim a VC (JSON) into the Passport Scorer database via an API call

  Scenario: Submit valid VC from passport
    Given I am a user that claims a stamp with our IAM server
    When the IAM server validates the conditions and creates the Stamp (VerifiedCredential)
    Then it stores the stamp in the DB Cache by posting it to the Scorer API URL
    And then it returns it to the Passport app
