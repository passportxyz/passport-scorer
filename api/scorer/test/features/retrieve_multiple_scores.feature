Feature: Retrieve Paginated List of Passport Scores Within a Community

As a developer using the API, I want to be able to read the logged Passport scores of multiple Ethereum addresses within a community that I manage, so that I can efficiently retrieve this information for my users.

Scenario: Retrieve logged Passport scores for Ethereum addresses within a community
  Given I have a community to which users have submitted passports
  When I make a request calling /score/community/{community-id} API endpoint with my API Key
  Then I get a paginated list of scores is returned for that community
