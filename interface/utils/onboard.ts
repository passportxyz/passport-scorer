import { init } from "@web3-onboard/react";
import walletConnectModule, {
  WalletConnectOptions,
} from "@web3-onboard/walletconnect";

import injectedModule from "@web3-onboard/injected-wallets";

const alchemyApiKey =
  process.env.NEXT_PUBLIC_PASSPORT_SCORER_ALCHEMY_API_KEY || "";

const walletConnectOptions: WalletConnectOptions = {
 projectId:
   (process.env.NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID as string) ||
   "default-project-id",
};

const onBoardExploreUrl =
  (process.env.NEXT_PUBLIC_WEB3_ONBOARD_EXPLORE_URL as string) ||
  "https://passport.gitcoin.co/";

const walletConnect = walletConnectModule(walletConnectOptions);
const injected = injectedModule();

const wallets = [injected, walletConnect];

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
  explore: onBoardExploreUrl,
  description:
    "Take control of your online identity by creating a decentralized record of your credentials. By collecting “stamps” of validation for your identity and online reputation, you can gain access to the most trustworthy web3 experiences and maximize your ability to benefit from platforms like Gitcoin Grants. The more you verify your identity, the more opportunities you will have to vote and participate across the web3.",
  recommendedInjectedWallets: [
    { name: "Coinbase", url: "https://wallet.coinbase.com/" },
    { name: "MetaMask", url: "https://metamask.io" },
  ],
};

const accountCenter = {
  desktop: {
    enabled: true,
  },
  mobile: {
    enabled: true,
    minimal: true,
  },
};

init({
  wallets,
  chains,
  appMetadata,
  accountCenter,
});
