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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const ethers_1 = __importDefault(require("ethers"));
const chainsauce_1 = require("chainsauce");
const postgres_1 = require("./storage/postgres");
function handleEvent(indexer, event) {
    return __awaiter(this, void 0, void 0, function* () {
        const db = indexer.storage;
    });
}
const provider = new ethers_1.default.providers.JsonRpcProvider("http://mynode.com");
const storage = new postgres_1.PostgresStorage("./data");
const indexer = (0, chainsauce_1.createIndexer)(provider, storage, handleEvent);
//# sourceMappingURL=index.js.map
