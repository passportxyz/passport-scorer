import ethers from "ethers";
import { createIndexer, Event, Indexer } from "chainsauce";
import { PostgresStorage } from "./storage/postgres";

import IDStakingABI from "./abis/IDStaking.json";
async function handleEvent(indexer: Indexer<PostgresStorage>, event: Event) {
  const db = indexer.storage;

  // switch (event.name) {
  //   case "UserCreated":
  //     // db.collection("users").insert({
  //     //   id: event.args.id,
  //     //   name: event.args.name
  //     // });
  //     break;

  //   case "UserUpdated":
  //     // db.collection("users").updateById(event.args.id, {
  //     //   name: event.args.name
  //     // });
  //     break;
  // }
}

const provider = new ethers.providers.JsonRpcProvider("http://mynode.com");
const storage = new PostgresStorage("./data");
const indexer = createIndexer(provider, storage, handleEvent);
