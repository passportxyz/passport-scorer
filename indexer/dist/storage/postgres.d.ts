import type { Storage, Subscription } from "chainsauce";
import { Client } from "pg";
export declare class PostgresStorage implements Storage {
    db: Client;
    constructor(connectionString: string);
    write?(): Promise<void>;
    read?(): Promise<void>;
    init(): Promise<void>;
    getSubscriptions(): Promise<Subscription[]>;
    setSubscriptions(subscriptions: Subscription[]): Promise<void>;
}
