DROP TABLE IF EXISTS user_permissions;
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS roles;

CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    FOREIGN KEY (role_id) REFERENCES roles (id)
);

CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE TABLE user_permissions (
    user_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, permission_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE TABLE vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    products TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    owner_user_id INTEGER,
    FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    vendor_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    FOREIGN KEY (vendor_id) REFERENCES vendors (id)
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'completed', 'cancelled')),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (product_id) REFERENCES products (id)
);

INSERT INTO roles (name) VALUES ('super_admin'), ('admin'), ('vendor'), ('customer');

INSERT INTO permissions (name, description) VALUES
    ('view_dashboard', 'View administration dashboard'),
    ('manage_vendors', 'Approve, reject, edit, and delete vendors'),
    ('manage_products', 'Approve, reject, edit, and delete products'),
    ('manage_orders', 'Monitor and update orders'),
    ('manage_payments', 'Manage payment settings and records'),
    ('view_analytics', 'View analytics and performance reports'),
    ('manage_settings', 'Change system-wide settings'),
    ('manage_own_products', 'Manage products owned by the vendor'),
    ('manage_own_orders', 'View and manage orders for the vendor');

INSERT INTO role_permissions (role_id, permission_id)
SELECT roles.id, permissions.id FROM roles, permissions
WHERE roles.name = 'admin' AND permissions.name IN ('view_dashboard', 'manage_vendors', 'manage_products', 'manage_orders', 'view_analytics');

INSERT INTO role_permissions (role_id, permission_id)
SELECT roles.id, permissions.id FROM roles, permissions
WHERE roles.name = 'vendor' AND permissions.name IN ('manage_own_products', 'manage_own_orders');

INSERT INTO role_permissions (role_id, permission_id)
SELECT roles.id, permissions.id FROM roles, permissions
WHERE roles.name = 'customer' AND permissions.name = 'view_dashboard' AND 1 = 0;

INSERT INTO vendors (name, email, products, status) VALUES
    ('Mara Studio', 'hello@marastudio.example', 'Arc desk lamp', 'approved'),
    ('Woven North', 'hello@wovennorth.example', 'Field notes tote', 'approved');

INSERT INTO products (name, price, vendor_id, status) VALUES
    ('Arc Desk Lamp', 84.00, 1, 'approved'),
    ('Field Notes Tote', 46.00, 2, 'approved'),
    ('Cedar + Smoke Candle', 28.00, 1, 'approved'),
    ('Alba Ceramic Mug', 32.00, 1, 'approved');

INSERT INTO users (name, email, password, role_id, status) VALUES
    ('Demo Customer', 'demo@rijoya.local', 'demo-password', (SELECT id FROM roles WHERE name = 'customer'), 'active'),
    ('Rijoya Super Admin', 'admin@rijoya.local', 'admin123', (SELECT id FROM roles WHERE name = 'super_admin'), 'active'),
    ('Rijoya Admin', 'ops@rijoya.local', 'admin123', (SELECT id FROM roles WHERE name = 'admin'), 'active');
