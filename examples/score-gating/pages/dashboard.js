import dstyles from "@/styles/Dashboard.module.css";
import styles from "@/styles/Home.module.css";
import Image from "next/image";
import Head from "next/head";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount } from "wagmi";
import Router from 'next/router'

export default function Dashboard() {
  const {address} = useAccount({
    onDisconnect() {
      Router.push("/")
    },
  });

  return (
    <>
    <Head>
      <title>Dashboard</title>
      <meta
        name="description"
        content="A sample app to demonstrate using the Gitcoin Passport Scorer API"
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
              src="/gitcoinWordLogo.svg"
              alt="Gitcoin Logo"
              className={styles.gitcoinLogo}
              width={150}
              height={34}
              priority
            />
          </a>
        </div>
        <ConnectButton />
      </div>
        <div className={dstyles.container}>
          <div className={dstyles.header}>
            <h1>Dashboard</h1>
            <p style={{marginTop: "10px"}}>
              You're seeing this page because your Passport score
              <br />
              was high enough for you to be signed in.
              <br />
              <br />
              Enjoy a collection of Solarpunk art.
            </p>
          </div>
          <div className={dstyles.photocontainer}>
            <Image src="/lunar1.png" width={629} height={629} alt="Solarpunk city" className={dstyles.photo}></Image>
            <Image src="/lunar2.png" width={629} height={629} alt="Solarpunk city" className={dstyles.photo}></Image>
            <Image src="/lunar3.png" width={629} height={629} alt="Solarpunk city" className={dstyles.photo}></Image>
            <Image src="/lunar4.png" width={629} height={629} alt="Solarpunk city" className={dstyles.photo}></Image>
            <Image src="/lunar5.png" width={629} height={629} alt="Solarpunk city" className={dstyles.photo}></Image>
            <Image src="/lunar6.png" width={629} height={629} alt="Solarpunk city" className={dstyles.photo}></Image>
          </div>
        </div>
    </main>
  </>
  )
}