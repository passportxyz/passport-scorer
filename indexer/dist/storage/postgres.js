"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.PostgresStorage = void 0;
const ethers_1 = require("ethers");
const pg_1 = require("pg");
class PostgresStorage {
    constructor(connectionString) {
        this.db = new pg_1.Client({
            connectionString,
        });
    }
    write() {
        throw new Error("Method not implemented.");
    }
    read() {
        throw new Error("Method not implemented.");
    }
    init() {
        return __awaiter(this, void 0, void 0, function* () {
            yield this.db.connect();
            yield this.db.query(`CREATE TABLE IF NOT EXISTS "__subscriptions" (
        "address" TEXT NOT NULL PRIMARY KEY,
        "abi" TEXT NOT NULL,
        "fromBlock" INTEGER NOT NULL
      )`);
            yield this.db.query(`CREATE TABLE IF NOT EXISTS "selfStake" (
        "roundId" INTEGER NOT NULL,
        "staker" TEXT NOT NULL,
        "amount" INTEGER NOT NULL,
        "staked" BOOLEAN NOT NULL
      )`);
            yield this.db.query(`CREATE TABLE IF NOT EXISTS "xStake" (
        "roundId" INTEGER NOT NULL,
        "staker" TEXT NOT NULL,
        "user" TEXT NOT NULL,
        "amount" INTEGER NOT NULL,
        "staked" BOOLEAN NOT NULL
      )`);
        });
    }
    getSubscriptions() {
        return __awaiter(this, void 0, void 0, function* () {
            const res = yield this.db.query("SELECT * FROM __subscriptions");
            return res.rows.map((sub) => ({
                address: sub.address,
                contract: new ethers_1.ethers.Contract(sub.address, JSON.parse(sub.abi)),
                fromBlock: sub.fromBlock,
            }));
        });
    }
    setSubscriptions(subscriptions) {
        return __awaiter(this, void 0, void 0, function* () {
            yield this.db.query("DELETE FROM __subscriptions");
            const insertQuery = "INSERT INTO __subscriptions (address, abi, fromBlock) VALUES ($1, $2, $3)";
            for (const sub of subscriptions) {
                yield this.db.query(insertQuery, [
                    sub.address,
                    JSON.stringify(sub.contract.interface.format(ethers_1.ethers.utils.FormatTypes.json)),
                    sub.fromBlock,
                ]);
            }
        });
    }
}
exports.PostgresStorage = PostgresStorage;
//# sourceMappingURL=postgres.js.map
