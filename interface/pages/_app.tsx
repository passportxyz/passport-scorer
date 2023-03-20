// --- React components/methods
import React, { useEffect, useState } from "react";

// -- React router
import { RouterProvider } from "react-router-dom";

// --- Styling & UI
import "../styles/globals.css";
import { ChakraProvider } from "@chakra-ui/react";

// --- Next components
import type { AppProps } from "next/app";
import Head from "next/head";
import ManageAccountCenter from "../components/ManageAccountCenter";
import RequireAuth from "../components/RequireAuth";

import { UserProvider } from "../context/userContext";

export default function App({ Component, pageProps }: AppProps) {
  const [isServer, setIsServer] = useState(true);
  useEffect(() => {
    setIsServer(false);
  }, []);
  if (isServer) return null;
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
              <div suppressHydrationWarning>
                {typeof window === "undefined" ? null : (
                  <Component {...pageProps} />
                )}
              </div>{" "}
            </RequireAuth>
          </ManageAccountCenter>
        </ChakraProvider>
      </UserProvider>
    </>
  );
}
