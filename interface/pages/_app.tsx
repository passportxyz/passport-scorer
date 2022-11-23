// --- React Methods
import React, { useState } from "react";

// --- Styling & UI
import "../styles/globals.css";
import "@rainbow-me/rainbowkit/styles.css";
import { ChakraProvider } from "@chakra-ui/react";

// --- Rainbowkit
import {
  connectorsForWallets,
  getDefaultWallets,
  RainbowKitProvider,
  lightTheme,
  ConnectButton,
  RainbowKitAuthenticationProvider,
  AuthenticationStatus,
} from "@rainbow-me/rainbowkit";
import { RainbowKitSiweNextAuthProvider } from "@rainbow-me/rainbowkit-siwe-next-auth";

// --- Next components
import type { AppProps } from "next/app";
import Head from "next/head";

// --- Wagmi
import { chain, configureChains, createClient, WagmiConfig } from "wagmi";
import { metaMaskWallet } from "@rainbow-me/rainbowkit/wallets";
import { alchemyProvider } from "wagmi/providers/alchemy";
import { publicProvider } from "wagmi/providers/public";

import { createAuthenticationAdapter } from "@rainbow-me/rainbowkit";
import { SiweMessage } from "siwe";

const SCORER_BACKEND = "http://localhost:8000/";

const authenticationAdapter = createAuthenticationAdapter({
  getNonce: async () => {
    const response = await fetch(`${SCORER_BACKEND}account/nonce`);
    return await response.text();
  },

  createMessage: ({ nonce, address, chainId }) => {
    return new SiweMessage({
      domain: window.location.host,
      address,
      statement: "Sign in with Ethereum to the app.",
      uri: window.location.origin,
      version: "1",
      chainId,
      nonce,
    });
  },

  getMessageBody: ({ message }) => {
    return message.prepareMessage();
  },

  verify: async ({ message, signature }) => {
    const verifyRes = await fetch(`${SCORER_BACKEND}account/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, signature }),
    });

    return Boolean(verifyRes.ok);
  },

  signOut: async () => {
    await fetch("/api/logout");
  },
});

const { chains, provider, webSocketProvider } = configureChains(
  [chain.mainnet],
  [
    alchemyProvider({
      apiKey: process.env.NEXT_PUBLIC_PASSPORT_SCORER_ALCHEMY_API_KEY || "",
    }),
    publicProvider(),
  ]
);

const { wallets } = getDefaultWallets({
  appName: "Passport Scorer as a Service",
  chains,
});

const passportScorerApp = {
  appName: "Passport Scorer as a Service",
};

const connectors = connectorsForWallets([
  ...wallets,
  {
    groupName: "Wallets",
    wallets: [metaMaskWallet({ chains })],
  },
]);

const wagmiClient = createClient({
  autoConnect: true,
  connectors,
  provider,
  webSocketProvider,
});

export default function App({ Component, pageProps }: AppProps) {
  // You'll need to resolve AUTHENTICATION_STATUS here
  // using your application's authentication system.
  // It needs to be either 'loading' (during initial load),
  // 'unathenticated' or 'authenticated'.
  const [authenticationStatus, setAuthenticationStatus] =
    useState<AuthenticationStatus>("unauthenticated");

  return (
    <>
      <Head>
        <link rel="shortcut icon" href="/favicon.ico" />
        <title>Passport Scorer</title>
      </Head>
      <WagmiConfig client={wagmiClient}>
        <RainbowKitAuthenticationProvider
          adapter={authenticationAdapter}
          status={authenticationStatus}
        >
          <RainbowKitProvider
            appInfo={passportScorerApp}
            chains={chains}
            modalSize="compact"
            theme={lightTheme({
              accentColor: "#757087",
              accentColorForeground: "white",
              borderRadius: "small",
              overlayBlur: "small",
              fontStack: undefined,
            })}
          >
            <ChakraProvider>
              <Component {...pageProps} />
            </ChakraProvider>
          </RainbowKitProvider>
        </RainbowKitAuthenticationProvider>
      </WagmiConfig>
    </>
  );
}
