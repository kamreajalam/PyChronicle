import sqlite3


class Database:

    def __init__(self, db_name="pychronicle.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            function TEXT,
            file TEXT,
            line INTEGER,
            variables TEXT
        )
        """)
        self.conn.commit()

    def insert_event(self, event, function, file, line, variables):
        self.cursor.execute("""
        INSERT INTO events(event, function, file, line, variables)
        VALUES (?, ?, ?, ?, ?)
        """, (event, function, file, line, variables))

        self.conn.commit()

    def close(self):
        self.conn.close()