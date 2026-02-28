from abc import ABC
import json
import duckdb

class Database():

    def __init__(self, dbpath: str = None):
        self.dbpath = dbpath or 'db/db.duckdb'

    def init(self):
        db = duckdb.connect(self.dbpath)
        db.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            url TEXT PRIMARY KEY,
            medicine_id TEXT,
            medicine_name TEXT NOT NULL,
            mrp REAL,
            pack_size_quantity TEXT,
            selling_price REAL,
            discount_percentage TEXT,
            source TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );    
        
        CREATE TABLE IF NOT EXISTS medicine_details (
            url TEXT PRIMARY KEY,
            source TEXT,
            scraped boolean DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS medicine_scraped_details (
            medicine_url TEXT PRIMARY KEY,
            medicine_name TEXT,
            medicine_composition TEXT,
            medicine_marketer TEXT,
            medicine_storage TEXT,
            medicine_mrp REAL,
            medicine_selling_price REAL,
            medicine_discount REAL,
            pack_size_information TEXT,
            substitutes TEXT,
            generic_alternative_available BOOLEAN,
            generic_alternative JSON,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS brand_searches (
            brand_name TEXT,
            source TEXT,
            scraped BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (brand_name, source)
        );
        """)
        
        # Migrations for existing tables
        try:
            db.execute("ALTER TABLE medicine_details ADD COLUMN source TEXT;")
        except:
            pass
        try:
            db.execute("ALTER TABLE medicine_scraped_details ADD COLUMN source TEXT;")
        except:
            pass
        try:
            db.execute("ALTER TABLE medicines ALTER medicine_id DROP NOT NULL;")
        except:
            pass
        pass


    def del_(self):
        db = duckdb.connect(self.dbpath)
        db.execute("DROP TABLE IF EXISTS medicines;")
        db.execute("DROP TABLE IF EXISTS medicine_details;")
        db.execute("DROP TABLE IF EXISTS medicine_scraped_details;")
        db.execute("DROP TABLE IF EXISTS brand_searches;")


    def insert_medicine(self, medicine, source):
        db = duckdb.connect(self.dbpath)
        db.execute(f"INSERT INTO medicines (url, medicine_id, medicine_name, mrp, pack_size_quantity, selling_price, discount_percentage, source) "
                   f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                   f"ON CONFLICT DO UPDATE "
                   f"SET url = EXCLUDED.url, "
                   f"medicine_id = EXCLUDED.medicine_id, "
                   f"medicine_name = EXCLUDED.medicine_name, "
                   f"mrp = EXCLUDED.mrp, "
                   f"pack_size_quantity = EXCLUDED.pack_size_quantity, "
                   f"selling_price = EXCLUDED.selling_price, "
                   f"discount_percentage = EXCLUDED.discount_percentage, "
                   f"source = EXCLUDED.source, "
                   f"updatedAt = current_localtimestamp()"
                   , (medicine['medicine_url'], medicine['medicine_id'], medicine['medicine_name'], medicine['mrp'], medicine['pack_size_quantity'], medicine['selling_price'], medicine['discount_percentage'], source))

        db.execute("INSERT INTO medicine_details (url, source) VALUES (?, ?) ON CONFLICT DO UPDATE SET scraped = FALSE, updatedAt = current_localtimestamp()", (medicine['medicine_url'], source))


    def insert_scraped_details(self, medicine, source):
        db = duckdb.connect(self.dbpath)
        db.execute(f"INSERT INTO medicine_scraped_details (medicine_url, medicine_name, medicine_composition, medicine_marketer, medicine_storage, medicine_mrp, medicine_selling_price, medicine_discount, pack_size_information, substitutes, generic_alternative_available, generic_alternative, source) "
                   f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                   f"ON CONFLICT DO UPDATE "
                   f"SET medicine_url = EXCLUDED.medicine_url, "
                   f"medicine_name = EXCLUDED.medicine_name, "
                   f"medicine_composition = EXCLUDED.medicine_composition, "
                   f"medicine_marketer = EXCLUDED.medicine_marketer, "
                   f"medicine_storage = EXCLUDED.medicine_storage, "
                   f"medicine_mrp = EXCLUDED.medicine_mrp, "
                   f"medicine_selling_price = EXCLUDED.medicine_selling_price, "
                   f"medicine_discount = EXCLUDED.medicine_discount, "
                   f"pack_size_information = EXCLUDED.pack_size_information, "
                   f"substitutes = EXCLUDED.substitutes, "
                   f"generic_alternative_available = EXCLUDED.generic_alternative_available, "
                   f"generic_alternative = EXCLUDED.generic_alternative,"
                   f"source = EXCLUDED.source,"
                   f"updatedAt = current_localtimestamp()"
                   , (medicine['medicine_url'], medicine['medicine_name'], medicine['medicine_composition'], medicine['medicine_marketer'], medicine['medicine_storage'], medicine['medicine_mrp'], medicine['medicine_selling_price'], medicine['medicine_discount'], medicine['pack_size_information'], str(medicine['substitutes']) if 'substitutes' in medicine else None, medicine.get('generic_alternative_available'), json.dumps(medicine.get('generic_alternative')) if medicine.get('generic_alternative') else None, source))

        self.update_scraped(medicine['medicine_url'])


    def mark_brand_as_searched(self, brand_name, source):
        db = duckdb.connect(self.dbpath)
        db.execute("INSERT INTO brand_searches (brand_name, source, scraped) VALUES (?, ?, TRUE) ON CONFLICT DO UPDATE SET updatedAt = current_localtimestamp()", (brand_name.upper(), source))


    def get_brand_search_status(self, brand_name, source):
        db = duckdb.connect(self.dbpath)
        res = db.execute("SELECT scraped FROM brand_searches WHERE brand_name = ? AND source = ?", (brand_name.upper(), source)).fetchone()
        return res[0] if res else False


    def get_brands(self, source=None):
        db = duckdb.connect(self.dbpath)
        query = """
            SELECT m.medicine_name, md.url, m.source
            FROM medicine_details md 
            JOIN medicines m ON md.url = m.url 
            WHERE md.scraped = FALSE
        """
        if source:
            query += f" AND md.source = '{source}'"
        return db.execute(query).df()


    def clear_pending_brands(self, source=None):
        db = duckdb.connect(self.dbpath)
        where_clause = "WHERE scraped = FALSE"
        if source:
            where_clause += f" AND source = '{source}'"
        
        db.execute(f"DELETE FROM medicines WHERE url IN (SELECT url FROM medicine_details {where_clause})")
        db.execute(f"DELETE FROM medicine_details {where_clause}")


    def get_medicine_details(self, medicine_url):
        db = duckdb.connect(self.dbpath)
        return db.execute("SELECT * FROM medicine_details WHERE url = ?", (medicine_url,)).df()


    def update_scraped(self, medicine_url):
        db = duckdb.connect(self.dbpath)
        db.execute("UPDATE medicine_details SET scraped = TRUE, updatedAt = current_localtimestamp() WHERE url = ?", (medicine_url,))


    def extract_scraped_data(self):
        db = duckdb.connect(self.dbpath)
        return db.execute("SELECT * FROM medicine_scraped_details").df()
