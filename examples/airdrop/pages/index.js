import Head from "next/head";
import Image from "next/image";
import { Inter } from "next/font/google";
import styles from "@/styles/Home.module.css";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import AirDrop from "../components/AirDrop";
import { useState, useEffect } from "react";
import axios from "axios";

const inter = Inter({ subsets: ["latin"] });

export default function Home() {
  const [theme, setTheme] = useState(null);

  useEffect(() => {
    async function getTheme() {
      const resp = await axios.get("/api/theme");
      if (resp.status !== 200) {
        console.error("failed to fetch theme");
      }
      console.log("resp: ", resp);
      setTheme(resp.data.theme);
    }
    getTheme();
  }, []);

  return (
    <>
      <Head>
        <title>Airdrop</title>
        <meta
          name="description"
          content="A sample app to demonstrate using the Gitcoin passport scorer API"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <main className={styles.main}>
        <div className={styles.description}>
          <div>
            <a
              href="https://www.gitcoin.co/"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Image
                src={
                  theme
                    ? `data:image/png;base64,${theme.image}`
                    : "/gitcoinWordLogo.svg"
                }
                alt="Gitcoin Logo"
                className={theme ? "" : styles.gitcoinLogo}
                width={150}
                height={34}
                priority
              />
            </a>
          </div>
          <ConnectButton />
        </div>
        <div className={styles.center}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              marginBottom: "35px",
            }}
          >
            <h1 style={{ fontFamily: "sans-serif", marginRight: "20px" }}>
              {theme?.name}
            </h1>
            <p style={{ marginTop: "10px", maxWidth: "800px" }}>
              {theme?.description}
            </p>
          </div>
          <AirDrop />
        </div>

        <div className={styles.grid} />
      </main>
    </>
  );
}
