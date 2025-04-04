import { createTestDIDSession } from "../utils/dids";
import { DID } from "dids";
import { BaseUser } from "./User";
import { Signer } from "ethers";
import { Wallet, providers } from "ethers";

const testPrivateKey = "0xc4aa93fe0b965ecaa4303fe3ef5554c428891b79d069f5b905397f286060007a";

export class PassportUIUser extends BaseUser {
  declare did: DID;
  declare address: string;
  declare signer: Signer;
  customizationPath = process.env.CUSTOMIZATION_PATH!;
  customProviderId = process.env.CUSTOM_PROVIDER_ID!;
  allowListName = process.env.ALLOW_LIST_NAME!;

  async init() {
    const wallet = new Wallet(testPrivateKey);
    await this.initFromWallet(wallet);
  }

  private async initFromWallet(wallet: Wallet) {
    const provider = new providers.AlchemyProvider("mainnet", process.env.ALCHEMY_API_KEY);

    const { did } = await createTestDIDSession({ wallet, provider });

    this.did = did;
    this.address = wallet.address.toLowerCase();
    this.signer = wallet;
  }

  static async createFromWallet(wallet: Wallet) {
    const user = new PassportUIUser();
    await user.initFromWallet(wallet);
    return user;
  }
}
