Feature: Deduplication rules
  The supported deduplication methods are: LIFO (other are coming later)

  Scenario: As a developer, I want to rely on LIFO as a default stamp deduplication rule
    Given that a Passport holder submits a stamp with a hash that a different Passport holder previously submitted to the community
    When we score the associated Passports, i.e., the Passports holding the stamps with identical hashes
    Then we don't recognize the version of the stamp that has been more recently submitted
    And score this Passport as if the stamp would be missing


