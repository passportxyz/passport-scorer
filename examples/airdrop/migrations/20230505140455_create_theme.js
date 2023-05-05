/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.up = function (knex) {
  knex.schema.hasTable("theme").then((exists) => {
    if (!exists) {
      return knex.schema.createTable("theme", (table) => {
        table.increments("id");
        table.string("name");
        table.string("description");
        table.binary("image");
      });
    }
  });
};

/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.down = function (knex) {};
