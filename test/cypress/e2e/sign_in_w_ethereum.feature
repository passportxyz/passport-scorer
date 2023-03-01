Feature: Sign In With Ethereum
  Given someone navigates to scorer.gitcoin.co
  When they click the "sign in with Ethereum" button
  Then the new authorization flow should be presented to connect a wallet and sign a Tx.
