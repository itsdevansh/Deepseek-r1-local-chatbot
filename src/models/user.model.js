// src/models/user.model.js
const db = require('../config/database');
const bcrypt = require('bcryptjs');

class User {
  static async create({ email, password, name, provider = 'local', providerId = null, creds=null }) {
    const hashedPassword = password ? await bcrypt.hash(password, 10) : null;
    
    const query = `
      INSERT INTO users (email, password, name, provider, provider_id, creds, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, NOW())
      RETURNING id, email, name, provider, creds;
    `;
    
    const values = [email, hashedPassword, name, provider, providerId, creds];
    const result = await db.query(query, values);
    return result.rows[0];
  }

  static async findByEmail(email) {
    const query = 'SELECT email, name, creds FROM users WHERE email = $1';
    const result = await db.query(query, [email]);
    return result.rows[0];
  }

  static async findByProviderId(provider, providerId) {
    const query = 'SELECT * FROM users WHERE provider = $1 AND provider_id = $2';
    const result = await db.query(query, [provider, providerId]);
    return result.rows[0];
  }

  static async updateCredByEmail(creds, email) {
    const query = 'UPDATE users SET creds = $1 WHERE email = $2';
    const result = await db.query(query, [creds, email]);
    return result.rows[0];
  }
}

module.exports = User;