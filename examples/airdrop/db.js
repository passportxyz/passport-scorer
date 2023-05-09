import config from "./knexfile";
import { knex } from "knex";

const db = knex(config[process.env.NODE_ENV || "development"]);

export default db;
