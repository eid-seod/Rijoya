DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

CREATE TABLE vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    products TEXT DEFAULT ''
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    vendor_id INTEGER NOT NULL,
    FOREIGN KEY (vendor_id) REFERENCES vendors (id)
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (product_id) REFERENCES products (id)
);

INSERT INTO vendors (name, email, products) VALUES
    ('Mara Studio', 'hello@marastudio.example', 'Arc desk lamp'),
    ('Woven North', 'hello@wovennorth.example', 'Field notes tote');

INSERT INTO products (name, price, vendor_id) VALUES
    ('Arc Desk Lamp', 84.00, 1),
    ('Field Notes Tote', 46.00, 2),
    ('Cedar + Smoke Candle', 28.00, 1),
    ('Alba Ceramic Mug', 32.00, 1);

INSERT INTO users (name, email, password) VALUES
    ('Demo Customer', 'demo@rijoya.local', 'demo-password');
