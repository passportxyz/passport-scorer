import { Page } from "../page";

export default class LandingPage extends Page {
  constructor() {
    super();
  }

  visit() {
    cy.visit("/");
  }

  signInWithEthereum() {
    cy.clearLocalStorage();
    this.initiateSignInWithEthereum();
    this.selectMetamaskWallet();
    cy.acceptMetamaskAccess({ signInSignature: true });
  }

  initiateSignInWithEthereum() {
    const siweButton = this.getSignInWithEthereumButton();
    siweButton.click();
  }

  selectMetamaskWallet() {
    const metamaskWallet = this.getMetamaskWalletOption();
    metamaskWallet.click();
  }

  getMetamaskWalletOption() {
    return cy.get("onboard-v2").shadow().contains("MetaMask");
  }

  getSignInWithEthereumButton() {
    const signInBtn = cy.get(
      'button[data-testid="connectWalletButtonDesktop"]'
    );

    signInBtn.should("be.visible");
    return signInBtn;
  }

  waitUntilSignedIn() {
    cy.waitUntil(() => {
      return cy.contains("Gitcoin Passport Scorer");
      // const walletAddress = this.header.getWalletAddress();
      // return walletAddress.should("exist");
    });
  }
}
