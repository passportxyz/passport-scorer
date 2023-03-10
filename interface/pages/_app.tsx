// --- React components/methods
import React, { useEffect, useState } from "react";

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

  // Authenticate the user -- interacts with the backend to GET the nonce, create & send back the SIWE message,
  // and receive a response

  return (
    <>
      <Head>
        <link rel="shortcut icon" href="/favicon.ico" />
        <title>Passport Scorer</title>
      </Head>

      <UserProvider>
        <ChakraProvider>
          <Component {...pageProps} />
        </ChakraProvider>
      </UserProvider>
    </>
  );
}
