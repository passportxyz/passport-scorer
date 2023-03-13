// --- React components/methods
import React, { useEffect, useState, useMemo, useRef } from "react";
import { initOnboard } from "../utils/onboard";

// --- Styling & UI
import "../styles/globals.css";
import { ChakraProvider } from "@chakra-ui/react";

// --- Next components
import type { AppProps } from "next/app";
import Head from "next/head";
import { useRouter } from "next/router";

import { UserProvider } from "../context/userContext";

const passportScorerApp = {
  appName: "Passport Scorer as a Service",
};

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    initOnboard("account-center-container");
    setReady(true);
  }, []);

  // Authenticate the user -- interacts with the backend to GET the nonce, create & send back the SIWE message,
  // and receive a response
  //

  return (
    <div className="relative">
      <Head>
        <link rel="shortcut icon" href="/favicon.ico" />
        <title>Passport Scorer</title>
      </Head>
      <div
        className="absolute top-0 left-20"
        id="account-center-container"
      ></div>
      {ready && (
        <UserProvider>
          <ChakraProvider>
            <Component {...pageProps} />
          </ChakraProvider>
        </UserProvider>
      )}
    </div>
  );
}
