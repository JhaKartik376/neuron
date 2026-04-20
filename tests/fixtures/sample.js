import { readFile } from 'fs/promises';
import path from 'path';

class UserService {
  constructor(db) {
    this.db = db;
  }

  async getUser(id) {
    return this.db.query('SELECT * FROM users WHERE id = ?', [id]);
  }

  async createUser(data) {
    const validated = this.validate(data);
    return this.db.insert('users', validated);
  }

  validate(data) {
    if (!data.name || !data.email) {
      throw new Error('Missing required fields');
    }
    return { ...data, createdAt: new Date() };
  }
}

function formatUser(user) {
  return {
    id: user.id,
    displayName: `${user.firstName} ${user.lastName}`,
    email: user.email,
  };
}

export { UserService, formatUser };
