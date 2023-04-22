import Head from "next/head";
import Image from "next/image";
import { Inter } from "next/font/google";
import styles from "@/styles/Dashboard.module.css";
import axios from "axios";
import { useState, useMemo } from "react";
import Table from "../../components/Table";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import AddAirdrop from "../../components/AddAirdrop";

const inter = Inter({ subsets: ["latin"] });

export default function Dashboard({ data }) {
  const [merkleRoot, setMerkleRoot] = useState("");
  const [airdropData, setAirdropData] = useState(data);
  const [showAddForm, setShowAddForm] = useState(false);

  async function getMerkleRoot() {
    const resp = await axios.get("/api/admin/merkle");
    setMerkleRoot(resp.data);
  }

  const columns = useMemo(() => [
    {
      Header: "ID",
      accessor: "id",
    },
    {
      Header: "Address",
      accessor: "address",
    },
    {
      Header: "Score",
      accessor: "score",
    },
    {
      Header: "Actions",
    },
  ]);

  function downloadData() {
    // Convert the data object to a JSON string
    const jsonData = JSON.stringify(airdropData, null, 2);

    // Create a Blob from the JSON string
    const blob = new Blob([jsonData], { type: "application/json" });

    // Generate a URL for the Blob
    const url = URL.createObjectURL(blob);

    // Create an invisible anchor element and set its attributes
    const link = document.createElement("a");
    link.href = url;
    link.download = "data.json";

    // Append the anchor element to the DOM, click it to trigger the download, and remove it
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Release the Blob URL
    URL.revokeObjectURL(url);
  }

  async function removeFromAirdrop(address) {
    console.log("removing from airdrop: ", address);
    const resp = await axios.post("/api/admin/remove", { address });
    console.log("resp: ", resp);
    if (resp.status === 200) {
      const newData = airdropData.filter((item) => item.address !== address);
      console.log("newData: ", newData);
      setAirdropData(newData);
    }
  }

  async function addToAirdrop(address) {
    if (address !== "" && address !== undefined) {
      try {
        console.log("adding to the airdrop: ", address);
        const resp = await axios.post("/api/admin/add", { address });
        console.log("add resp: ", resp);
        if (resp.status === 200) {
          const newData = [...airdropData, resp.data.added];
          console.log("newData: ", newData);
          setAirdropData(newData);
        }
      } catch (e) {
        console.error(e);
      }
    }
  }

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
        <div>
          <h4 className={styles.h4}>
            Total eligible addresses: {airdropData.length}
          </h4>
          <div style={{ marginTop: "10px" }}>
            <div>
              <button
                disabled={airdropData?.length === 0}
                className={styles.btn}
                onClick={downloadData}
              >
                Download Airdrop Data
              </button>
              <button
                disabled={airdropData?.length === 0}
                className={styles.btn}
                style={{ marginLeft: "10px" }}
                onClick={getMerkleRoot}
              >
                Generate Merkle Root
              </button>
              <button
                className={styles.btn}
                style={{ marginLeft: "10px" }}
                onClick={() => setShowAddForm(true)}
              >
                Manual Add
              </button>
            </div>
          </div>
          {merkleRoot !== "" ? (
            <p className={styles.p} style={{ marginTop: "10px" }}>
              Merkle Root: {merkleRoot}
            </p>
          ) : null}
          {showAddForm ? (
            <AddAirdrop
              add={(address) => addToAirdrop(address)}
              cancel={() => setShowAddForm(false)}
            />
          ) : null}
          {airdropData?.length > 0 ? (
            <Table
              columns={columns}
              data={airdropData}
              removeFromAirdrop={removeFromAirdrop}
            />
          ) : (
            <p style={{ marginTop: "20px;" }}>
              No eligible addresses to display
            </p>
          )}
        </div>

        <div className={styles.grid} />
      </main>
    </>
  );
}

export async function getServerSideProps(context) {
  const { data } = await axios.get("http://localhost:3000/api/admin/airdrop");
  // Return the fetched data as props
  return {
    props: {
      data,
    },
  };
}
