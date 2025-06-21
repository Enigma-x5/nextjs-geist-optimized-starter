// Authentication Configuration
// In production, these should be stored in environment variables or a secure database

export interface User {
  username: string;
  password: string; // In production, this should be hashed
  role: 'admin' | 'operator' | 'viewer';
  permissions: string[];
}

// Demo users - In production, store these in a secure database with hashed passwords
export const DEMO_USERS: User[] = [
  {
    username: 'admin',
    password: 'password123', // In production: hash this password
    role: 'admin',
    permissions: ['view_all', 'search', 'export', 'manage_users']
  },
  {
    username: 'operator',
    password: 'operator123',
    role: 'operator', 
    permissions: ['view_all', 'search', 'export']
  },
  {
    username: 'viewer',
    password: 'viewer123',
    role: 'viewer',
    permissions: ['view_limited', 'search']
  }
];

// JWT Configuration
export const JWT_CONFIG = {
  secret: process.env.JWT_SECRET || 'your-secret-key-change-in-production',
  expiresIn: '24h'
};

// Password validation rules
export const PASSWORD_RULES = {
  minLength: 8,
  requireUppercase: true,
  requireLowercase: true,
  requireNumbers: true,
  requireSpecialChars: false
};

// Session configuration
export const SESSION_CONFIG = {
  maxAge: 24 * 60 * 60 * 1000, // 24 hours in milliseconds
  secure: process.env.NODE_ENV === 'production',
  httpOnly: true
};
