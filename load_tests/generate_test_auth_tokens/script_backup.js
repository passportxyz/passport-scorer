const { ethers } = require("ethers");
// import { DIDSession } from "did-session";
// import type { AuthMethod } from "@didtools/cacao";

// import { EthereumWebAuth, getAccountId } from require("@didtools/pkh-ethereum");

console.log("ethers:", ethers);

const mnemonicPhrase =
  "chief loud snack trend chief net field husband vote message decide replace";

// Generate multiple wallets from the HDNode instance
const wallets = [];
for (let i = 0; i < 10; i++) {
  const path = "m/44'/60'/0'/0/" + i;
  const wallet = ethers.Wallet.fromMnemonic(mnemonicPhrase, path);
  wallets.push(wallet);
  console.log("wallet", wallet.address);
}

import("./bridge.js").then(({ Eip1193Bridge }) => {
  import("caip").then(({ AccountId }) => {
    import("did-session").then(({ DIDSession }) => {
      import("@didtools/pkh-ethereum").then(
        ({ EthereumNodeAuth, getAccountId }) => {
          async function createTokens() {
            const provider = new ethers.providers.AlchemyProvider(
              "mainnet",
              "5QPthzD45A2kb7VKlphviV2voxiIEMqL"
            );

            const wallet = ethers.Wallet.fromMnemonic(mnemonicPhrase);
            const eip1193Provider = new Eip1193Bridge(wallet, provider);
            console.log("Wallet: ", wallet);
            eip1193Provider
              .send("eth_chainId")
              .then((chainId) => {
                console.log("Chain Id: ", chainId);
              })
              .catch((err) => {
                console.error("!!! error getting accountId", err);
              });
            console.log("Wallet: ", wallet);
            console.log("wallet.provider: ", eip1193Provider);
            const accountId = new AccountId({
              chainId: "eip155:1",
              address: wallet.address,
            });

            EthereumNodeAuth.getAuthMethod(
              eip1193Provider,
              accountId,
              "gitcoin-load"
            ).then((authMethod) => {
              console.log("accountId", accountId);

              DIDSession.authorize(authMethod, {
                resources: ["ceramic://*"],
                Domain: "gitcoin-load-test",
              }).then((session) => {
                const newSessionStr = session.serialize();
                const did = session.did;
                console.log("-----------------------------------------");
                console.log("newSessionStr: ", newSessionStr);
                console.log("-----------------------------------------");
                console.log("session.cacao: ", session.cacao);
                console.log("-----------------------------------------");

                const nonce = 1234;
                const payloadToSign = { nonce };

                // sign the payload as dag-jose
                console.log("payloadToSign: ", payloadToSign);
                did
                  .createDagJWS(payloadToSign)
                  .then(({ jws, cacaoBlock }) => {
                    console.log({ jws, cacaoBlock });
                    // Get the JWS & serialize it (this is what we would send to the BE)
                    // const { link, payload, signatures } = jws;
                  })
                  .catch((err) => {
                    console.error("!!! error getting accountId", err);
                    console.log("!!! error getting accountId", err);
                  });
              });
            });
          }

          createTokens().catch((err) => {
            console.error("!!! error getting accountId", err);
            console.log("!!! error getting accountId", err);
          });
        }
      );
    });
  });
});
