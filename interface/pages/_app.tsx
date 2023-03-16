// --- React components/methods
import React from "react";

// --- Styling & UI
import "../styles/globals.css";
import { ChakraProvider } from "@chakra-ui/react";

// --- Next components
import type { AppProps } from "next/app";
import Head from "next/head";
import ManageAccountCenter from "../components/ManageAccountCenter";
import RequireAuth from "../components/RequireAuth";

import { UserProvider } from "../context/userContext";

const passportScorerApp = {
  appName: "Passport Scorer as a Service",
};
export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <link rel="shortcut icon" href="/favicon.ico" />
        <title>Passport Scorer</title>
      </Head>

      <UserProvider>
        <ChakraProvider>
          <ManageAccountCenter>
            <RequireAuth>
              <Component {...pageProps} />
            </RequireAuth>
          </ManageAccountCenter>
        </ChakraProvider>
      </UserProvider>
    </>
  );
}
