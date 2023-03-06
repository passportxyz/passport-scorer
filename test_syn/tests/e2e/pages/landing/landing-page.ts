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
    // cy.switchToMetamaskWindow();
    if (Cypress.env("SKIP_METAMASK_CONNECT") != "1") {
      cy.acceptMetamaskAccess().should("be.true");
    }
    cy.confirmMetamaskSignatureRequest().should("be.true");
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
      return cy.contains("Dashboard");
      // const walletAddress = this.header.getWalletAddress();
      // return walletAddress.should("exist");
    });
  }
}
