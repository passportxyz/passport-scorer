import { WalletState } from '@web3-onboard/core';
import { ethers } from 'ethers';
import { SiweMessage } from 'siwe';
import {getNonce} from './account-requests'

const getSiweMessage = async (wallet: WalletState, address: string) => {
  const nonce = await getNonce();

  const message = new SiweMessage({
    domain: window.location.host,
    address,
    statement: "Sign in with Ethereum to the app.",
    uri: window.location.origin,
    version: "1",
    chainId: Number(wallet.chains[0].id),
    nonce,
  });

  return message;
}

export const initiateSIWE = async (wallet: WalletState) => {
  const provider = new ethers.providers.Web3Provider(wallet.provider, 'any')
  const signer = provider.getSigner()
  const address = await signer.getAddress()

  const siweMessage = await getSiweMessage(wallet, address);
  const preparedMessage = siweMessage.prepareMessage();

  const signature = await signer.signMessage(preparedMessage);

  return { siweMessage, signature };
}
