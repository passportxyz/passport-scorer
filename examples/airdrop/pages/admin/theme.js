import Head from "next/head";
import Image from "next/image";
import styles from "@/styles/Dashboard.module.css";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useState } from "react";
import axios from "axios";

export default function Theme() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!name || !description || !file) {
      alert("Please fill in all fields and select a file to upload");
      return;
    }

    const formData = new FormData();
    formData.append("name", name);
    formData.append("description", description);
    formData.append("file", file);

    try {
      const response = await axios.post("/api/admin/theme", formData);
      console.log("response: ", response);
    } catch (error) {
      console.error(error);
    }
  };

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
        <div
          style={{
            width: "100%",
            maxWidth: "1100px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <div style={{ marginBottom: "35px" }}>
            <h1
              style={{
                color: "rgb(111,63,245)",
                fontFamily: "sans-serif",
                marginBottom: "10px",
              }}
            >
              Customize Theme
            </h1>
            <p>Change the name, description, and image your users will see.</p>
          </div>
          <form
            style={{
              display: "flex",
              flexDirection: "column",
              maxWidth: "500px",
              justifyContent: "center",
            }}
            onSubmit={handleSubmit}
          >
            <label htmlFor="name">Name:</label>
            <input
              style={{ marginBottom: "20px", padding: "5px 10px" }}
              type="text"
              id="name"
              name="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />

            <label htmlFor="description">Description:</label>
            <textarea
              style={{ marginBottom: "20px", padding: "5px 10px" }}
              id="description"
              name="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
            />

            <label htmlFor="file">Image:</label>
            <input
              type="file"
              id="file"
              name="file"
              onChange={(e) => setFile(e.target.files[0])}
              required
            />

            <button
              style={{ marginTop: "30px" }}
              className={styles.btn}
              type="submit"
            >
              Upload
            </button>
          </form>
        </div>

        <div className={styles.grid} />
      </main>
    </>
  );
}
