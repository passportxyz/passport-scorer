
# Running this example

1. Install `serve` by running `npm install --global serve` in your terminal. `serve` is a simple, zero-configuration command-line HTTP server. Find out more about `serve` [here](https://www.npmjs.com/package/serve).
2. Open a terminal, navigate to the directory containing the `index.html` file for this example.
3. Run `serve` and follow the instructions in the terminal to start the local HTTP server.
4. In your web browser, navigate to the URL provided by `serve` to view the example.

# About this example

This example demonstrates how to use the Gitcoin Passport Scoring API to score a user's Passport. It includes a form for the developer to input their community ID and API key, which they can obtain from their [Gitcoin Passport Scoring dashboard](https://www.scorer.gitcoin.co/). When the "Submit for scoring" button is clicked, the provided community ID and API key are used to make a GET request to the Gitcoin Passport Scoring API. The response from the API, which includes the user's Passport score, is then displayed on the page.

The example also includes a "Connect" button that, when clicked, uses the Ethers.js library to request the user's Ethereum address from a Web3 provider (such as MetaMask). The user's address is then displayed on the page.

This example makes use of the following libraries:

- [Bootstrap](https://getbootstrap.com/): A popular front-end component library for styling and layout.
- [Axios](https://github.com/axios/axios): A library for making HTTP requests.
- [Ethers.js](https://docs.ethers.org/v5/): A library for working with Ethereum addresses and contracts.
