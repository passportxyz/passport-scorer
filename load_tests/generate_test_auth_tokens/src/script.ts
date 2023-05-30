import { ethers } from "ethers";
import { DIDSession } from "did-session";
import type { AuthMethod } from "@didtools/cacao";
import { EthereumWebAuth, getAccountId } from "@didtools/pkh-ethereum";

// ethers.fromMnemonic
console.log("ethers:", ethers.HDNodeWallet.fromMnemonic);

const mnemonic = ethers.Mnemonic.fromPhrase(
  "chief loud snack trend chief net field husband vote message decide replace"
);

const hdNode = ethers.HDNodeWallet.fromMnemonic(mnemonic);

//  ⇒ "m/44'/60'/0'/0/0"
console.log({
  hdNode,
  address: hdNode.address,
  privateKey: hdNode.privateKey,
});

// Generate multiple wallets from the HDNode instance
const wallets = [];
for (let i = 0; i < 1000; i++) {
  const path = "m/44'/60'/0'/0/" + i;
  const wallet = hdNode.derivePath(path);
  wallets.push(wallet);
  console.log("wallet", wallet.address);
}

// async function createTokens() {
//   const accountId = await getAccountId(hdNode, hdNode.address);
//   const authMethod = await EthereumWebAuth.getAuthMethod(hdNode, accountId);
// }

// createTokens();
