
// import Web3 from "web3";

// const web3 = new Web3(Web3.givenProvider || "ws://localhost:8545");
// const HDWalletProvider = require('@truffle/hdwallet-provider');
import { Wallet} from "ethers";
import { SiweMessage } from "siwe";

const SCORER_BACKEND = "http://localhost:8000/"

console.log("DEFINING COMMANDS ...")
Cypress.Commands.add('siwe', async () => {
    console.log("Signing in with ETH");
    const response = await fetch(`${SCORER_BACKEND}account/nonce`);
    const nonce = (await response.json()).nonce;
    console.log("nonce: ", nonce);
    const wallet = Wallet.fromMnemonic("chief loud snack trend chief net field husband vote message decide replace");

    const address = wallet.address;
    const chainId = 1;
    const message = {
        domain: window.location.host,
        address,
        statement: "Sign in with Ethereum to the app.",
        uri: window.location.origin,
        version: "1",
        chainId,
        nonce,
        issuedAt: new Date().toISOString()
      };
    const siweMessage= new SiweMessage(message);

    const msgToSign = siweMessage.toMessage();

    const signature = await wallet.signMessage(msgToSign);
    console.log("signature", signature);

    const verifyRes = await fetch(`${SCORER_BACKEND}account/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, signature }),
      });

      if (verifyRes.ok) {
        const data = await verifyRes.json();

        // store JWT access token in LocalStorage
        localStorage.setItem("access-token", data.access);
      }
})
