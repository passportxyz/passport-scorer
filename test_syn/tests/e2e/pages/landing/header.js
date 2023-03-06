import Page from '../page';
export default class Header extends Page {
  getConnectWalletBtn() {
    return cy.get('#app button:nth-child(3)').first();
  }
  getWalletAddress() {
    // eslint-disable-next-line ui-testing/no-css-page-layout-selector
    return cy.get('#app button:nth-child(4) > p');
  }
}
