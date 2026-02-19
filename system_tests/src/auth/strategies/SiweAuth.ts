import axios, { isAxiosError } from "axios";
import { Wallet } from "ethers";
import { TestRequestOptionsNoAuth } from "../../types";
import { BaseAuthStrategy } from "./strategy";

interface SiweAuthConfig {
  wallet: Wallet;
}

export class SiweAuth extends BaseAuthStrategy {
  wallet: Wallet;
  accessToken?: string;

  constructor({ wallet }: SiweAuthConfig) {
    super({ name: "siwe-auth" });
    this.wallet = wallet;
  }

  async applyAuth(options: TestRequestOptionsNoAuth): Promise<TestRequestOptionsNoAuth> {
    if (!this.accessToken) {
      this.accessToken = await getAccessToken(this.wallet);
    }

    return {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${this.accessToken}`,
      },
    };
  }
}

const getAccessToken = async (wallet: Wallet): Promise<string> => {
  const baseUrl = process.env.SCORER_API_BASE_URL;
  const address = await wallet.getAddress();

  // Get nonce
  let nonce: string;
  try {
    const nonceResponse = await axios.get(`${baseUrl}/account/nonce`);
    nonce = nonceResponse.data.nonce;
  } catch (error) {
    if (isAxiosError(error)) {
      throw new Error(`Failed to get nonce: ${error.message}, status: ${error.response?.status}`);
    }
    throw error;
  }

  // Build SIWE message fields
  // The SIWE domain must match the frontend domain (app.*), not the API domain (api.*)
  const apiHost = new URL(baseUrl!).host;
  const domain = apiHost.replace(/^api\./, "app.");
  const issuedAt = new Date().toISOString();
  const expirationTime = new Date(Date.now() + 5 * 60 * 1000).toISOString();
  const statement = `Welcome to Gitcoin Passport Scorer! This request will not trigger a blockchain transaction or cost any gas fees. Your authentication status will reset in 24 hours. Wallet Address: ${address}. Nonce: ${nonce}`;

  const uri = `https://${domain}`;

  const message = {
    domain,
    address,
    statement,
    uri,
    version: "1",
    chainId: 1,
    nonce,
    issuedAt,
    expirationTime,
  };

  // Format EIP-4361 message text for signing
  const messageText = [
    `${domain} wants you to sign in with your Ethereum account:`,
    address,
    "",
    statement,
    "",
    `URI: ${uri}`,
    `Version: 1`,
    `Chain ID: 1`,
    `Nonce: ${nonce}`,
    `Issued At: ${issuedAt}`,
    `Expiration Time: ${expirationTime}`,
  ].join("\n");

  const signature = await wallet.signMessage(messageText);

  // Authenticate
  let accessToken: string;
  try {
    const authResponse = await axios.post(`${baseUrl}/ceramic-cache/authenticate`, {
      message,
      signature,
    });
    accessToken = authResponse.data?.access as string;
  } catch (error) {
    if (isAxiosError(error)) {
      throw new Error(
        `Failed to authenticate with SIWE for ${address}: ${error.message}, status: ${error.response?.status}`
      );
    }
    throw error;
  }

  if (!accessToken) {
    throw new Error("No access token received from SIWE authentication");
  }

  return accessToken;
};
