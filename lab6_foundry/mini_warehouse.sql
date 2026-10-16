-- FreshCart mini warehouse for Part 6: few enough rows to check every answer by hand.
-- The same traps as the full warehouse: two test accounts, an old orders table, order lines that
-- multiply an order, refund claims with capitalised statuses, and an order with two claims.

CREATE TABLE dim_customer (
  customer_id INT PRIMARY KEY, name VARCHAR(40), city VARCHAR(20), region VARCHAR(10),
  signup_date DATE, status VARCHAR(10), is_internal BIT NOT NULL DEFAULT 0);

CREATE TABLE dim_restaurant (
  restaurant_id INT PRIMARY KEY, name VARCHAR(40), city VARCHAR(20), cuisine VARCHAR(20));

CREATE TABLE orders (
  order_id INT PRIMARY KEY, customer_id INT, restaurant_id INT, order_date DATE, amount DECIMAL(10,2));

CREATE TABLE orders_v2 (
  order_id INT PRIMARY KEY, customer_id INT, restaurant_id INT, order_date DATE,
  order_value DECIMAL(10,2), status VARCHAR(12));

CREATE TABLE order_items (
  item_id INT PRIMARY KEY, order_id INT, item_name VARCHAR(30), quantity INT, item_price DECIMAL(10,2));

CREATE TABLE fact_refund_claim (
  claim_id INT PRIMARY KEY, order_id INT, customer_id INT, claim_date DATE, reason VARCHAR(30),
  amount DECIMAL(10,2), status VARCHAR(14));

INSERT INTO dim_customer VALUES
 (1, 'Test Account A', 'Delhi', 'North', '2023-01-01', 'active', 1),
 (2, 'Test Account B', 'Mumbai', 'West', '2023-01-01', 'active', 1),
 (3, 'Asha', 'Delhi', 'North', '2023-04-11', 'active', 0),
 (4, 'Ravi', 'Pune', 'West', '2023-06-02', 'churned', 0),
 (5, 'Meera', 'Bengaluru', 'South', '2023-07-19', 'inactive', 0),
 (6, 'Kabir', 'Delhi', 'North', '2023-09-30', 'active', 0),
 (7, 'Sara', 'Mumbai', 'West', '2023-11-05', 'churned', 0),
 (8, 'Dev', 'Hyderabad', 'South', '2024-01-20', 'active', 0);

INSERT INTO dim_restaurant VALUES
 (1, 'Biryani House', 'Delhi', 'Biryani'), (2, 'Dosa Corner', 'Bengaluru', 'South Indian'),
 (3, 'Pizza Point', 'Mumbai', 'Pizza');

INSERT INTO orders_v2 VALUES
 (101, 3, 1, '2024-03-02', 500.00, 'delivered'),
 (102, 4, 2, '2024-03-05', 300.00, 'delivered'),
 (103, 5, 2, '2024-03-09', 450.00, 'cancelled'),
 (104, 1, 3, '2024-03-10', 999.00, 'delivered'),
 (105, 6, 1, '2024-03-14', 250.00, 'delivered'),
 (106, 7, 3, '2024-03-18', 700.00, 'delivered'),
 (107, 2, 3, '2024-03-21', 999.00, 'delivered'),
 (108, 8, 2, '2024-03-25', 350.00, 'delivered'),
 (109, 3, 1, '2024-03-28', 200.00, 'cancelled'),
 (110, 4, 2, '2024-03-30', 400.00, 'delivered'),
 (201, 3, 1, '2024-05-03', 600.00, 'delivered'),
 (202, 5, 2, '2024-05-07', 350.00, 'delivered'),
 (203, 1, 3, '2024-05-08', 999.00, 'delivered'),
 (204, 6, 1, '2024-05-12', 280.00, 'delivered'),
 (205, 8, 2, '2024-05-19', 420.00, 'cancelled'),
 (206, 2, 3, '2024-05-22', 999.00, 'delivered'),
 (207, 7, 3, '2024-05-27', 510.00, 'delivered');

-- The old copy: an earlier export that stopped being updated, with fewer rows.
INSERT INTO orders VALUES
 (101, 3, 1, '2024-03-02', 500.00), (102, 4, 2, '2024-03-05', 300.00),
 (105, 6, 1, '2024-03-14', 250.00), (106, 7, 3, '2024-03-18', 700.00), (108, 8, 2, '2024-03-25', 350.00),
 (201, 3, 1, '2024-05-03', 600.00), (202, 5, 2, '2024-05-07', 350.00), (204, 6, 1, '2024-05-12', 280.00);

-- Order lines for the March orders: several lines per order, so a join repeats the order.
INSERT INTO order_items VALUES
 (1, 101, 'Chicken biryani', 1, 320.00), (2, 101, 'Raita', 1, 80.00),
 (3, 102, 'Masala dosa', 2, 120.00),
 (4, 103, 'Idli', 3, 150.00),
 (5, 104, 'Margherita', 1, 999.00),
 (6, 105, 'Veg biryani', 1, 180.00), (7, 105, 'Gulab jamun', 1, 50.00),
 (8, 106, 'Farmhouse pizza', 1, 450.00), (9, 106, 'Garlic bread', 1, 150.00), (10, 106, 'Cola', 2, 40.00),
 (11, 107, 'Pepperoni', 1, 999.00),
 (12, 108, 'Rava dosa', 1, 300.00),
 (13, 109, 'Kebab', 1, 200.00),
 (14, 110, 'Uttapam', 1, 220.00), (15, 110, 'Filter coffee', 2, 70.00);

INSERT INTO fact_refund_claim VALUES
 (1, 101, 3, '2024-03-04', 'Missing item', 100.00, 'Approved'),
 (2, 101, 3, '2024-03-06', 'Missing item', 100.00, 'Declined'),
 (3, 106, 7, '2024-03-20', 'Cold food', 150.00, 'Approved'),
 (4, 104, 1, '2024-03-12', 'Test claim', 999.00, 'Approved'),
 (5, 110, 4, '2024-03-31', 'Late delivery', 80.00, 'Under review');

-- Give the Function App read-only access, signing in with its own Azure identity (no password).
-- Replace freshcart-lab6 with your Function App's name if it differs. Run these two lines after the tables are loaded.
-- CREATE USER [freshcart-lab6] FROM EXTERNAL PROVIDER;
-- ALTER ROLE db_datareader ADD MEMBER [freshcart-lab6];
