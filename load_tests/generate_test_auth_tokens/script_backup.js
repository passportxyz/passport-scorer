const { ethers } = require("ethers");
const axios = require("axios");
const fs = require("fs");

const mnemonicPhrase =
  process.env.MNEMONIC ||
  "chief loud snack trend chief net field husband vote message decide replace";
const alchemyApiKey = process.env.ALCHEMY_API_KEY;
const numAccounts = Number.parseInt(process.env.NUM_ACCOUNTS) || 100;

// Generate multiple wallets from the HDNode instance
const wallets = [];
for (let i = 0; i < numAccounts; i++) {
  const path = "m/44'/60'/0'/0/" + i;
  const wallet = ethers.Wallet.fromMnemonic(mnemonicPhrase, path);
  wallets.push(wallet);
  console.log("wallet", i, wallet.address);
}

import("./bridge.js").then(({ Eip1193Bridge }) => {
  import("caip").then(({ AccountId }) => {
    import("did-session").then(({ DIDSession }) => {
      import("@didtools/pkh-ethereum").then(
        ({ EthereumNodeAuth, getAccountId }) => {
          import("@didtools/cacao").then(({ Cacao }) => {
            async function createTokens() {
              const provider = new ethers.providers.AlchemyProvider(
                "mainnet",
                alchemyApiKey
              );

              function getAuthTokenForwallet(wallet) {
                return new Promise((resolve, reject) => {
                  axios
                    .get("https://api.staging.scorer.gitcoin.co/account/nonce")
                    .then((res) => {
                      const nonce = res.data.nonce;

                      // const wallet = ethers.Wallet.fromMnemonic(mnemonicPhrase, "m/44'/60'/0'/0/" + i);
                      // const wallet = wallets[i];
                      const eip1193Provider = new Eip1193Bridge(
                        wallet,
                        provider
                      );
                      console.log("Wallet: ", wallet);
                      eip1193Provider
                        .send("eth_chainId")
                        .then((chainId) => {
                          console.log("Chain Id: ", chainId);
                        })
                        .catch((err) => {
                          console.error("!!! error getting accountId", err);
                          reject(err);
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
                          console.log(
                            "-----------------------------------------"
                          );
                          console.log("newSessionStr: ", newSessionStr);
                          console.log(
                            "-----------------------------------------"
                          );
                          console.log("session.cacao: ", session.cacao);
                          console.log(
                            "-----------------------------------------"
                          );

                          const payloadToSign = { nonce };

                          // sign the payload as dag-jose
                          console.log("payloadToSign: ", payloadToSign);
                          did
                            .createDagJWS(payloadToSign)
                            .then(({ jws, cacaoBlock }) => {
                              console.log({ jws, cacaoBlock });
                              // Get the JWS & serialize it (this is what we would send to the BE)
                              // const { link, payload, signatures } = jws;

                              // sign the payload as dag-jose

                              // Get the JWS & serialize it (this is what we would send to the BE)
                              const { link, payload, signatures } = jws;

                              if (cacaoBlock !== undefined) {
                                const cacao = Cacao.fromBlockBytes(
                                  cacaoBlock
                                ).then((cacao) => {
                                  const issuer = cacao.p.iss;
                                  const payloadForVerifier = {
                                    signatures: signatures,
                                    payload: payload,
                                    cid: Array.from(link ? link.bytes : []),
                                    cacao: Array.from(
                                      cacaoBlock ? cacaoBlock : []
                                    ),
                                    issuer,
                                    nonce: nonce,
                                  };
                                  try {
                                    const authResponse = axios
                                      .post(
                                        `https://api.staging.scorer.gitcoin.co/ceramic-cache/authenticate`,
                                        payloadForVerifier
                                      )
                                      .then((authResponse) => {
                                        const accessToken =
                                          authResponse.data.access;
                                        console.log(
                                          "accessToken: ",
                                          accessToken
                                        );
                                        resolve({
                                          address: wallet.address,
                                          accessToken: accessToken,
                                          payloadForVerifier
                                        });
                                      });
                                  } catch (error) {
                                    const msg = `Failed to authenticate user with did: ${did.parent}`;
                                    reject(err);
                                  }
                                });
                              }
                            })
                            .catch((err) => {
                              console.error("!!! error getting accountId", err);
                              console.log("!!! error getting accountId", err);
                              reject(err);
                            });
                        });
                      });
                    });
                });
              }

              const walletCreationPromises = wallets.map((wallet) => {
                return getAuthTokenForwallet(wallet);
              });

              Promise.allSettled(walletCreationPromises).then((results) => {
                console.log("results:", results);
                const userTokens = results.reduce((acc, result) => {
                  if (result.status === "fulfilled") {
                    acc[result.value.address] = result.value.accessToken;
                  }
                  return acc;
                }, {});
                let data = JSON.stringify(userTokens);
                console.log("num tokens:", Object.keys(userTokens).length);
                fs.writeFileSync("user-tokens.json", data);
              });
            }

            createTokens().catch((err) => {
              console.error("!!! error getting accountId", err);
              console.log("!!! error getting accountId", err);
            });
          });
        }
      );
    });
  });
});
