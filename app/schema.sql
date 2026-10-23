CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    variant TEXT NOT NULL,
    description TEXT NOT NULL,
    image TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price > 0)
);
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    total BIGINT NOT NULL CHECK (total > 0),
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_user_created ON orders(user_key, created_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    variant TEXT NOT NULL,
    unit_price INTEGER NOT NULL CHECK (unit_price > 0),
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 99)
);
CREATE INDEX IF NOT EXISTS order_items_order ON order_items(order_id);
