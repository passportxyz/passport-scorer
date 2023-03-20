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

import { UserProvider } from "../context/userContext";

export default function App({ Component, pageProps }: AppProps) {
  //  Following guide from https://colinhacks.com/essays/building-a-spa-with-nextjs to turn nextjs app into spa
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
            <div suppressHydrationWarning>
              {typeof window === "undefined" ? null : (
                <Component {...pageProps} />
              )}
            </div>{" "}
          </ManageAccountCenter>
        </ChakraProvider>
      </UserProvider>
    </>
  );
}
