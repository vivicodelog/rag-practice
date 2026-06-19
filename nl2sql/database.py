"""
SQLite 连接管理和建表逻辑
"""
import sqlite3

DB_PATH = "d:/rag-project/nl2sql/bookstore.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（每次调用返回新连接）"""
    # 这里写：connect 到 DB_PATH，设置 row_factory = sqlite3.Row（让查询结果能按列名访问）
    # 注意：sqlite3.connect() 的默认返回值类型是 tuple，设置了 row_factory 才能 dict 风格访问
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """建表：authors → books → customers → orders → order_items

    外键关系：
      books.author_id → authors.author_id
      orders.customer_id → customers.customer_id
      order_items.order_id → orders.order_id
      order_items.book_id → books.book_id
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. 开启外键约束（SQLite 默认关闭，需要 PRAGMA 开启）
    # 2. 建表 authors：author_id INTEGER PRIMARY KEY AUTOINCREMENT, name, country, birth_year
    # 3. 建表 books：book_id INTEGER PRIMARY KEY AUTOINCREMENT, title, author_id, price, stock, category
    # 4. 建表 customers：customer_id INTEGER PRIMARY KEY AUTOINCREMENT, name, email, city, join_date
    # 5. 建表 orders：order_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id, order_date, total_amount，外键 customer_id → customers
    # 6. 建表 order_items：item_id INTEGER PRIMARY KEY AUTOINCREMENT, order_id, book_id, quantity, price，外键 order_id → orders, book_id → books
    # 建表语句用 triple quotes 包起来，保持可读性
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("""CREATE TABLE IF NOT EXISTS authors (
        author_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        country TEXT,
        birth_year INTEGER
        );"""
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS books (
        book_id INTEGER PRIMARY KEY AUTOINCREMENT, 
        title TEXT NOT NULL,                  
        author_id INTEGER NOT NULL,
        price REAL,
        stock INTEGER,
        category TEXT
        );"""
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        city TEXT,
        join_date DATE
        );"""
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        order_date DATE,
        total_amount REAL,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );"""
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER ,
        book_id INTEGER,
        quantity INTEGER,
        price REAL,                   
        FOREIGN KEY (order_id) REFERENCES orders(order_id),             
        FOREIGN KEY (book_id) REFERENCES books(book_id)
        );"""
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS column_meta (     
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        column_name  TEXT NOT NULL,
        display_name TEXT NOT NULL, 
        UNIQUE(table_name, column_name)
        );"""
    )
    conn.commit()    # 提交
    cursor.close()   # 关游标
    conn.close()     # 关连接

def close(conn: sqlite3.Connection | None):
    """安全关闭连接"""
    if conn:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成")
