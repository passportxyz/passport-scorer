/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.up = function (knex) {
  knex.schema.hasTable("airdrop_addresses").then((exists) => {
    if (!exists) {
      return knex.schema.createTable("airdrop_addresses", (table) => {
        table.increments("id");
        table.string("address");
        table.float("score");
      });
    }
  });
};

/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.down = function (knex) {
  knex.schema.dropTableIfExists("airdrop_addresses");
};
