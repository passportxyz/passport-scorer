import styles from "@/styles/Dashboard.module.css";
import { useState } from "react";

export default function AddAirdrop({ cancel, add }) {
  const [address, setAddress] = useState("");

  return (
    <div
      style={{
        marginTop: "20px",
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <input
        onChange={(e) => setAddress(e.target.value)}
        style={{
          padding: "7px 5px",
          borderRadius: "10px",
          marginRight: "10px",
        }}
        placeholder="0x..."
        type="text"
      />
      <button onClick={() => add(address)} className={styles.btn} type="submit">
        Add
      </button>
      <button
        onClick={cancel}
        style={{ marginLeft: "10px" }}
        className={styles.btn}
        type="button"
      >
        Cancel
      </button>
    </div>
  );
}
