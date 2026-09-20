DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    products TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected'))
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

INSERT INTO vendors (name, email, products, status) VALUES
    ('Mara Studio', 'hello@marastudio.example', 'Arc desk lamp', 'approved'),
    ('Woven North', 'hello@wovennorth.example', 'Field notes tote', 'approved');

INSERT INTO products (name, price, vendor_id, status) VALUES
    ('Arc Desk Lamp', 84.00, 1, 'approved'),
    ('Field Notes Tote', 46.00, 2, 'approved'),
    ('Cedar + Smoke Candle', 28.00, 1, 'approved'),
    ('Alba Ceramic Mug', 32.00, 1, 'approved');

INSERT INTO users (name, email, password, is_admin) VALUES
    ('Demo Customer', 'demo@rijoya.local', 'demo-password', 0),
    ('Rijoya Super Admin', 'admin@rijoya.local', 'admin123', 1);
