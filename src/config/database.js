// src/config/database.js
const { Pool } = require("pg");
require("dotenv").config();

try {
  const pool = new Pool({
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    database: process.env.DB_NAME,
  });
  module.exports = {
    query: (text, params) => pool.query(text, params),
  };
} catch (error) {
  console.log(error);
}
