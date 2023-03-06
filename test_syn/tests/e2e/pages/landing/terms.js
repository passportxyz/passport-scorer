import Page from '../page';
export default class Terms extends Page {
  getTermsModal() {
    return cy.get('.chakra-modal__body > div');
  }
  getAcceptTermsButton() {
    return cy.get('.chakra-modal__content > button');
  }
}
