const sqlite3 = require("sqlite3");
const { open } = require("sqlite");

async function initializeDatabase() {
  // Open the SQLite database
  const db = await open({
    filename: "airdrop.db",
    driver: sqlite3.Database,
  });

  // Create tables if they don't exist
  await db.exec(`
    CREATE TABLE IF NOT EXISTS airdrop_addresses (
      id INTEGER PRIMARY KEY,
      address TEXT,
      score REAL
    );
  `);

  // Close the database connection
  await db.close();
}

module.exports = { initializeDatabase };
