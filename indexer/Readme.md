# Ethereum Event Listener with Postgres

## Overview

This Rust project listens to events emitted by a specific Ethereum smart contract and stores them in a PostgreSQL database. It uses the `ethers-rs` library for Ethereum interaction and `tokio-postgres` for database operations.

The smart contract events we're interested in are `selfStake` and `xStake`, each having specific parameters that are stored in the PostgreSQL database.

## Dependencies

- **Rust** (latest stable version)
- **PostgreSQL** (latest stable version)
- [`dotenv`](https://crates.io/crates/dotenv) for environment variable management
- [`tokio`](https://crates.io/crates/tokio) for asynchronous runtime
- [`tokio-postgres`](https://crates.io/crates/tokio-postgres) for interacting with PostgreSQL
- [`ethers`](https://crates.io/crates/ethers) for Ethereum interaction
- [`eyre`](https://crates.io/crates/eyre) for error handling

## Setup

### Environment Variables

Create a `.env` file in the root directory and add the following:

\```env
RPC_URL=your_ethereum_websockets_rpc_url
DATABASE_URL=your_postgresql_database_url
```

Replace `your_ethereum_rpc_url` and `your_postgresql_database_url` with your Ethereum RPC Websockets URL and PostgreSQL database URL, respectively.

### PostgreSQL

Make sure you have PostgreSQL installed and running. Create a new database and user if needed.

### Rust and Cargo

If you don't have Rust and Cargo installed, you can install them from [here](https://rustup.rs/).

## Running the Project

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/yourrepository.git
   ```

2. **Navigate into the project directory**:

   ```bash
   cd yourrepository
   ```

3. **Build the project**:

   ```bash
   cargo build
   ```

4. **Run the project**:

   ```bash
   cargo run
   ```

The program will start listening for `selfStake` and `xStake` events from the specified smart contract starting from a specific block number. Events will be stored in the PostgreSQL database as they are detected.

## Further Work

1. Implement more comprehensive error-handling.
2. Allow listening to multiple contracts.
3. Implement data validation and type-checking before inserting into the database.
