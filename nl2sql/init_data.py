"""
插入测试数据：作者 → 书籍 → 客户 → 订单 → 订单明细

在 database.init_db() 之后运行
"""
import sqlite3
from datetime import datetime, timedelta
import random
from database import get_connection, close


def seed_authors(cursor: sqlite3.Cursor):
    """插入作者数据"""
    # 写 6 个作者：三体刘慈欣（中国）、百年孤独马尔克斯（哥伦比亚）、
    # 挪威的森林村上春树（日本）、活着余华（中国）、
    # 1984 乔治奥威尔（英国）、百年孤独拉美文学
    # (name, country, birth_year)
    authors = [
        ("刘慈欣", "中国", 1963),
        ("加西亚·马尔克斯", "哥伦比亚", 1927),
        ("村上春树", "日本", 1949),
        ("余华", "中国", 1960),
        ("乔治·奥威尔", "英国", 1903),
        ("J.K.罗琳", "英国", 1965),
    ]
    # 用 cursor.executemany() 插入，SQL 用 INSERT INTO authors VALUES (NULL, ?, ?, ?)
    # 不写 VALUES (?, ?, ?) 是为了跳过 author_id，让数据库自增
    cursor.executemany("INSERT INTO authors VALUES (NULL, ?, ?, ?)", authors)



def seed_books(cursor: sqlite3.Cursor):
    """插入书籍数据"""
    # 每本书记录 (title, author_id, price, stock, category)
    # 刘慈欣（author_id = 1）：三体（science_fiction, 68, 50）、三体2黑暗森林（science_fiction, 72, 40）、三体3死神永生（science_fiction, 78, 30）
    # 马尔克斯（author_id = 2）：百年孤独（literature, 55, 20）、霍乱时期的爱情（literature, 48, 15）
    # 村上春树（author_id = 3）：挪威的森林（literature, 42, 25）、海边的卡夫卡（literature, 52, 18）
    # 余华（author_id = 4）：活着（literature, 35, 60）、许三观卖血记（literature, 38, 30）
    # 乔治·奥威尔（author_id = 5）：1984（science_fiction, 45, 35）、动物庄园（literature, 30, 45）
    # J.K.罗琳（author_id = 6）：哈利波特与魔法石（fantasy, 58, 80）、哈利波特与密室（fantasy, 62, 65）
    books = [
        ("三体", 1, 68, 50, "science_fiction"),
        ("三体2：黑暗森林", 1, 72, 40, "science_fiction"),
        ("三体3：死神永生", 1, 78, 30, "science_fiction"),
        ("百年孤独", 2, 55, 20, "literature"),
        ("霍乱时期的爱情", 2, 48, 15, "literature"),
        ("挪威的森林", 3, 42, 25, "literature"),
        ("海边的卡夫卡", 3, 52, 18, "literature"),
        ("活着", 4, 35, 60, "literature"),
        ("许三观卖血记", 4, 38, 30, "literature"),
        ("1984", 5, 45, 35, "science_fiction"),
        ("动物庄园", 5, 30, 45, "literature"),
        ("哈利波特与魔法石", 6, 58, 80, "fantasy"),
        ("哈利波特与密室", 6, 62, 65, "fantasy"),
    ]
    cursor.executemany("INSERT INTO books VALUES (NULL, ?, ?, ?, ?, ?)", books)


def seed_customers(cursor: sqlite3.Cursor):
    """插入客户数据"""
    # 5 个客户：张三（北京）、李四（上海）、王五（广州）、赵六（深圳）、陈七（杭州）
    # (name, email, city, join_date)
    # join_date 用 datetime.now().strftime()
    customers = [
        ("张三", "张三@example.com", "北京", datetime.now().strftime("%Y-%m-%d")),
        ("李四", "李四@example.com", "上海", datetime.now().strftime("%Y-%m-%d")),
        ("王五", "王五@example.com", "广州", datetime.now().strftime("%Y-%m-%d")),
        ("赵六", "赵六@example.com", "深圳", datetime.now().strftime("%Y-%m-%d")),
        ("陈七", "陈七@example.com", "杭州", datetime.now().strftime("%Y-%m-%d")),
    ]
    cursor.executemany("INSERT INTO customers VALUES (NULL, ?, ?, ?, ?)", customers)

def seed_orders(cursor: sqlite3.Cursor):
    """插入订单数据

    先插入 order，拿到 order_id，再插入对应的 order_items
    所以这里既插 orders 也插 order_items，两条一起在一个函数里
    """
    # 张三（customer_id=1）：2024-01-15 买三体(1) + 百年孤独(2)，totoal=68+55=123
    # 张三：2024-03-20 买活着(1)，total=35
    # 李四（customer_id=2）：2024-02-10 买挪威的森林(1) + 1984(1)，total=42+45=87
    # 王五（customer_id=3）：2024-04-05 买三体(2) + 黑暗森林(1)，total=68*2+72=208
    # 赵六（customer_id=4）：2024-05-12 买哈利波特与魔法石(1) + 哈利波特与密室(1)，total=58+62=120
    # 陈七（customer_id=5）：2024-06-01 买霍乱时期的爱情(1) + 海边的卡夫卡(1) + 动物庄园(1)，total=48+52+30=130

    # 对每一条：
    #   cursor.execute("INSERT INTO orders VALUES (NULL, ?, ?, ?)", (customer_id, order_date, total))
    #   order_id = cursor.lastrowid  ← 取出刚插入的自增 id
    #   cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, book_id, qty, price))
    # 第一步：插订单
    cursor.execute("INSERT INTO orders VALUES (NULL, ?, ?, ?)", (1, "2024-01-15", 178))
    # 第二步：问数据库刚才的 ID
    order_id = cursor.lastrowid          # ← 这个就是刚插的 order_id
    # 第三步：用这个 ID 插明细
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 1, 1, 68))
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 4, 2, 55))
    cursor.execute("INSERT INTO orders VALUES (NULL, ?, ?, ?)", (1, "2024-03-20", 35))
    # 第二步：问数据库刚才的 ID
    order_id = cursor.lastrowid          # ← 这个就是刚插的 order_id
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 8, 1, 35))
    #李四
    cursor.execute("INSERT INTO orders VALUES (NULL, ?, ?, ?)", (2, "2024-02-10", 87))
    order_id = cursor.lastrowid          # ← 这个就是刚插的 order_id
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 6, 1, 42))
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 10, 1, 45))
    #王五
    cursor.execute("INSERT INTO orders VALUES (NULL, ?, ?, ?)", (3, "2024-04-05", 208))
    order_id = cursor.lastrowid          # ← 这个就是刚插的 order_id
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 1, 2, 68))
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 2, 1, 72))
    # 赵六
    cursor.execute("INSERT INTO orders VALUES (NULL, ?, ?, ?)", (4, "2024-05-12", 120))
    order_id = cursor.lastrowid          # ← 这个就是刚插的 order_id
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 12, 1, 58))
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 13, 1, 62))

    # 陈七
    cursor.execute("INSERT INTO orders VALUES (NULL, ?, ?, ?)", (5, "2024-06-01", 130))
    order_id = cursor.lastrowid          # ← 这个就是刚插的 order_id
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 5, 1, 48))
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 7, 1, 52))
    cursor.execute("INSERT INTO order_items VALUES (NULL, ?, ?, ?, ?)", (order_id, 11, 1, 30))

def main():
    conn = get_connection()
    cursor = conn.cursor()

    print("正在插入作者...")
    seed_authors(cursor)
    print("正在插入书籍...")
    seed_books(cursor)
    print("正在插入客户...")
    seed_customers(cursor)
    print("正在插入订单...")
    seed_orders(cursor)

    conn.commit()
    close(conn)
    print("测试数据插入完成！")


if __name__ == "__main__":
    main()
