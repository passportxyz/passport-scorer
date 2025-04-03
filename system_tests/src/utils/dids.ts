import { DIDSession } from "did-session";
import { Wallet, providers } from "ethers";
import { AccountId } from "caip";
import { EthereumNodeAuth } from "@didtools/pkh-ethereum";
import { Eip1193Bridge } from "./bridge";
import { DID } from "dids";
import { Cacao } from "@didtools/cacao";

// Helper function to create a new DID for testing
export const createTestDIDSession = async ({ wallet, provider }: { wallet: Wallet; provider: providers.Provider }) => {
  const address = wallet.address;

  const accountId = new AccountId({
    chainId: "eip155:1",
    address,
  });

  const eip1193Provider = new Eip1193Bridge(wallet, provider);

  const authMethod = await EthereumNodeAuth.getAuthMethod(eip1193Provider, accountId, "system-test");

  const session = await DIDSession.authorize(authMethod, {
    resources: ["ceramic://*"],
    domain: "system-test",
  });

  return {
    session,
    did: session.did,
  };
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const createSignedPayload = async (did: DID, data: any) => {
  const { jws, cacaoBlock } = await did.createDagJWS(data);

  expect(Boolean(cacaoBlock)).toBe(true);

  const { link, payload, signatures } = jws;

  const cacao = await Cacao.fromBlockBytes(cacaoBlock!);
  const issuer = cacao.p.iss;

  return {
    signatures: signatures,
    payload: payload,
    cid: Array.from(link ? link.bytes : []),
    cacao: Array.from(cacaoBlock ? cacaoBlock : []),
    issuer,
  };
};
