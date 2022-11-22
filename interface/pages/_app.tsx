// --- Styling & UI
import "../styles/globals.css";
import "@rainbow-me/rainbowkit/styles.css";
import { ChakraProvider } from "@chakra-ui/react";

// --- Rainbowkit
import {
  connectorsForWallets,
  getDefaultWallets,
  RainbowKitProvider,
} from "@rainbow-me/rainbowkit";
import { RainbowKitSiweNextAuthProvider } from '@rainbow-me/rainbowkit-siwe-next-auth';

// --- Next components
import type { AppProps } from "next/app";
import Head from "next/head";

// --- Wagmi
import {
  chain,
  configureChains,
  createClient,
  WagmiConfig
} from 'wagmi';
import {
  metaMaskWallet,
} from '@rainbow-me/rainbowkit/wallets';
import { alchemyProvider } from 'wagmi/providers/alchemy';
import { publicProvider } from 'wagmi/providers/public';

const { chains, provider, webSocketProvider } = configureChains(
  [
    chain.mainnet,
  ],
  [
    alchemyProvider({ apiKey: process.env.NEXT_PUBLIC_PASSPORT_SCORER_ALCHEMY_API_KEY || "" }),
    publicProvider(),
  ]
);

const { wallets } = getDefaultWallets({
  appName: 'Passport Scorer as a Service',
  chains,
});

const passportScorerApp = {
  appName: 'Passport Scorer as a Service',
};

const connectors = connectorsForWallets([
  ...wallets,
  {
    groupName: 'Wallets',
    wallets: [
      metaMaskWallet({ chains })
    ],
  },
]);

const wagmiClient = createClient({
  autoConnect: true,
  connectors,
  provider,
  webSocketProvider,
});

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <link rel="shortcut icon" href="/favicon.ico" />
        <title>Passport Scorer</title>
      </Head>
      <WagmiConfig client={wagmiClient}>
        <RainbowKitProvider appInfo={passportScorerApp} chains={chains}>
          <ChakraProvider>
            <Component {...pageProps} />
          </ChakraProvider>
        </RainbowKitProvider>
      </WagmiConfig>
    </>
  );
}
