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

const INTERCOM_APP_ID = process.env.NEXT_PUBLIC_INTERCOM_APP_ID || "";

// Type definition for the window object
declare global {
  interface Window {
    intercomSettings?: {
      api_base: string;
      app_id: string;
    };
    Intercom: any;
  }
}

export default function App({ Component, pageProps }: AppProps) {
  //  Following guide from https://colinhacks.com/essays/building-a-spa-with-nextjs to turn nextjs app into spa
  const [isServer, setIsServer] = useState(true);
  useEffect(() => {
    setIsServer(false);
  }, []);
  //adding intercom widget
  useEffect(() => {
    if (typeof window !== "undefined") {
      window.intercomSettings = {
        api_base: "https://api-iam.intercom.io",
        app_id: INTERCOM_APP_ID,
      };
      (function () {
        var w: any = window;
        var ic = w.Intercom;
        if (typeof ic === "function") {
          ic("reattach_activator");
          ic("update", w.intercomSettings);
        } else {
          var d = document;
          var i = function () {
            // @ts-ignore
            i.c(arguments);
          };
          // @ts-ignore
          i.q = [];
          // @ts-ignore
          i.c = function (args) {
            // @ts-ignore
            i.q.push(args);
          };
          w.Intercom = i;
          var l = function () {
            var s = d.createElement("script");
            s.type = "text/javascript";
            s.async = true;
            s.src = "https://widget.intercom.io/widget/" + INTERCOM_APP_ID;
            var x = d.getElementsByTagName("script")[0];
            x.parentNode?.insertBefore(s, x);
          };
          if (document.readyState === "complete") {
            l();
          } else if (w.attachEvent) {
            w.attachEvent("onload", l);
          } else {
            w.addEventListener("load", l, false);
          }
        }
      })();
    }
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
