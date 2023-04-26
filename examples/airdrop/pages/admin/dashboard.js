import Head from "next/head";
import Image from "next/image";
import { Inter } from "next/font/google";
import styles from "@/styles/Dashboard.module.css";
import axios from "axios";
import { useState, useMemo } from "react";
import Table from "../../components/Table";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import AddAirdrop from "../../components/AddAirdrop";
import InfoCard from "../../components/InfoCard";
import {
  faPeopleGroup,
  faGaugeSimple,
  faLayerGroup,
} from "@fortawesome/free-solid-svg-icons";

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
    const resp = await axios.post("/api/admin/remove", { address });
    if (resp.status === 200) {
      const newData = airdropData.filter((item) => item.address !== address);
      setAirdropData(newData);
    }
  }

  async function addToAirdrop(address) {
    if (address !== "" && address !== undefined) {
      try {
        const resp = await axios.post("/api/admin/add", { address });
        if (resp.status === 200) {
          const newData = [...airdropData, resp.data.added];
          setAirdropData(newData);
        }
      } catch (e) {
        console.error(e);
      }
    }
  }

  function averageScore() {
    const total = airdropData.reduce((acc, item) => {
      return acc + item.score;
    }, 0);
    return (total / airdropData.length).toFixed(2);
  }

  function medianScore() {
    const sorted = airdropData.sort((a, b) => a.score - b.score);
    const middle = Math.floor(sorted.length / 2);
    if (sorted.length % 2 === 0) {
      return ((sorted[middle].score + sorted[middle - 1].score) / 2).toFixed(2);
    }
    return sorted[middle].score.toFixed(2);
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
        <div style={{ width: "100%", maxWidth: "1100px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "45px",
            }}
          >
            <InfoCard
              title="Total Allowlisted"
              icon={faPeopleGroup}
              value={airdropData?.length ? airdropData.length : 0}
            />
            <InfoCard
              title="Average Score"
              icon={faGaugeSimple}
              value={averageScore()}
            />
            <InfoCard
              title="Median Score"
              icon={faLayerGroup}
              value={medianScore()}
            />
          </div>
          <div
            style={{
              marginTop: "10px",
              display: "flex",
              justifyContent: "flex-end",
            }}
          >
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
          {merkleRoot !== "" ? (
            <p
              className={styles.p}
              style={{ marginTop: "10px", textAlign: "right" }}
            >
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
