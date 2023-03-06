import Page from '../page';

export default class Onboard extends Page {
  getBrowserWalletBtn() {
    return cy.get('onboard-v2').shadow().findByText('MetaMask');
  }
}
