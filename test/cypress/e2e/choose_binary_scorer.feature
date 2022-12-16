
Feature: Choose Binary Scorer (#778)
  Scenario: I want to choose the Gitcoin Binary Community Score
    Given that I'm a developer and have setup a community
    When I see the scoring options I can select for that community
    Then I see the Gitcoin Binary Community Score as an option, i.e., the binary output version of the of the default Gitcoin Community Score
