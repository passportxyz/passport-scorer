import "@synthetixio/synpress/support/index";

import { Wallet } from "ethers";
import { SiweMessage } from "siwe";

const SCORER_BACKEND = Cypress.env("SCORER_BACKEND");

console.log("DEFINING COMMANDS ...");
Cypress.Commands.add("createScorerSession", async () => {
  console.log("Signing in with ETH");
  const response = await fetch(`${SCORER_BACKEND}account/nonce`);
  const nonce = (await response.json()).nonce;
  console.log("nonce: ", nonce);
  const wallet = Wallet.fromMnemonic(
    "test test test test test test test test test test test junk"
  );

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
    issuedAt: new Date().toISOString(),
  };
  const siweMessage = new SiweMessage(message);

  const msgToSign = siweMessage.toMessage();

  const signature = await wallet.signMessage(msgToSign);
  console.log("signature", signature);

  const verifyRes = await fetch(`${SCORER_BACKEND}account/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, signature }),
  });
  console.log({ verifyRes });

  if (verifyRes.ok) {
    const data = await verifyRes.json();

    // store JWT access token in LocalStorage
    localStorage.setItem("access-token", data.access);
    // Store also the wallet details for blocknative in LocalStorage
    localStorage.setItem("connectedWallets", JSON.stringify(["MetaMask"]));
  }
});
