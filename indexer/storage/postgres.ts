import type { Storage, Subscription } from "chainsauce";
import { ethers } from "ethers";
import { Client } from "pg";

export class PostgresStorage implements Storage {
  db: Client;

  constructor(connectionString: string) {
    this.db = new Client({
      connectionString,
    });
  }

  write?(): Promise<void> {
    throw new Error("Method not implemented.");
  }
  read?(): Promise<void> {
    throw new Error("Method not implemented.");
  }

  async init() {
    await this.db.connect();
    await this.db.query(
      `CREATE TABLE IF NOT EXISTS "__subscriptions" (
        "address" TEXT NOT NULL PRIMARY KEY,
        "abi" TEXT NOT NULL,
        "fromBlock" INTEGER NOT NULL
      )`
    );

    // Create selfStake table
    await this.db.query(
      `CREATE TABLE IF NOT EXISTS "selfStake" (
        "roundId" INTEGER NOT NULL,
        "staker" TEXT NOT NULL,
        "amount" INTEGER NOT NULL,
        "staked" BOOLEAN NOT NULL
      )`
    );

    // Create xStake table
    await this.db.query(
      `CREATE TABLE IF NOT EXISTS "xStake" (
        "roundId" INTEGER NOT NULL,
        "staker" TEXT NOT NULL,
        "user" TEXT NOT NULL,
        "amount" INTEGER NOT NULL,
        "staked" BOOLEAN NOT NULL
      )`
    );
  }

  async getSubscriptions(): Promise<Subscription[]> {
    const res = await this.db.query("SELECT * FROM __subscriptions");
    return res.rows.map(
      (sub: { address: string; abi: string; fromBlock: number }) => ({
        address: sub.address,
        contract: new ethers.Contract(sub.address, JSON.parse(sub.abi)),
        fromBlock: sub.fromBlock,
      })
    );
  }

  async setSubscriptions(subscriptions: Subscription[]): Promise<void> {
    await this.db.query("DELETE FROM __subscriptions");

    const insertQuery =
      "INSERT INTO __subscriptions (address, abi, fromBlock) VALUES ($1, $2, $3)";

    for (const sub of subscriptions) {
      await this.db.query(insertQuery, [
        sub.address,
        JSON.stringify(
          sub.contract.interface.format(ethers.utils.FormatTypes.json)
        ),
        sub.fromBlock,
      ]);
    }
  }
}
