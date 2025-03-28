import { PassportUIUser } from "./PassportUIUser";
import { RegistryAPIUser } from "./RegistryAPIUser";
import { BaseUser } from "./User";
import { Signer } from "ethers";

export class EmbedUser extends BaseUser {
  declare apiKey: string;
  declare scorerId: string;
  declare address: string;
  declare signer: Signer;

  async init() {
    const passportUIUser = await PassportUIUser.get();
    const registryAPIUser = await RegistryAPIUser.get();

    this.apiKey = registryAPIUser.apiKey;
    this.scorerId = registryAPIUser.scorerId;
    this.address = passportUIUser.address;
    this.signer = passportUIUser.signer;
  }
}
