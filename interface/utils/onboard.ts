import { init } from "@web3-onboard/react";
import walletConnectModule from "@web3-onboard/walletconnect";
import coinbaseModule from "@web3-onboard/coinbase";
import ledgerModule from "@web3-onboard/ledger";
import injectedModule from "@web3-onboard/injected-wallets";

const alchemyApiKey =
  process.env.NEXT_PUBLIC_PASSPORT_SCORER_ALCHEMY_API_KEY || "";

const walletConnect = walletConnectModule();
const injected = injectedModule();
const coinbase = coinbaseModule();
const ledger = ledgerModule();

const wallets = [walletConnect, injected, coinbase, ledger];

const chains = [
  {
    id: "0x1",
    token: "ETH",
    label: "Ethereum Mainnet",
    rpcUrl: `https://eth-mainnet.g.alchemy.com/v2/${alchemyApiKey}`,
  },
];

const appMetadata = {
  name: "Passport Scorer",
  icon: "/assets/gitcoinLogoDark.svg",
  logo: "/assets/gitcoinLogoDark.svg",
  description:
    "Take control of your online identity by creating a decentralized record of your credentials. By collecting “stamps” of validation for your identity and online reputation, you can gain access to the most trustworthy web3 experiences and maximize your ability to benefit from platforms like Gitcoin Grants. The more you verify your identity, the more opportunities you will have to vote and participate across the web3.",
  recommendedInjectedWallets: [
    { name: "Coinbase", url: "https://wallet.coinbase.com/" },
    { name: "MetaMask", url: "https://metamask.io" },
  ],
};

init({
  wallets,
  chains,
  appMetadata,
  accountCenter: {
    desktop: {
      enabled: true,
      // minimal: false,
    },
    mobile: {
      enabled: true,
      minimal: true,
    }
  },
});
