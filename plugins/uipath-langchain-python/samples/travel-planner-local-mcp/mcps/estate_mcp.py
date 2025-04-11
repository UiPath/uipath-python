import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP instance
mcp = FastMCP("Real Estate Database 🏠")

# Database setup
DB_PATH = "real_estate.db"


def initialize_database():
    """Create database and tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create properties table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        zip_code TEXT NOT NULL,
        price REAL NOT NULL,
        bedrooms INTEGER NOT NULL,
        bathrooms REAL NOT NULL,
        sq_feet INTEGER NOT NULL,
        property_type TEXT NOT NULL,
        year_built INTEGER,
        description TEXT,
        listed_date TEXT
    )
    """)

    conn.commit()
    conn.close()


def populate_sample_data():
    """Add sample real estate data if the database is empty"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM properties")
    count = cursor.fetchone()[0]

    if count == 0:
        # Sample properties
        properties = [
            {
                "address": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zip_code": "94105",
                "price": 1250000,
                "bedrooms": 3,
                "bathrooms": 2.5,
                "sq_feet": 1800,
                "property_type": "Condo",
                "year_built": 2010,
                "description": "Modern condo with bay views",
                "listed_date": "2025-03-01",
            },
            {
                "address": "456 Oak Ave",
                "city": "New York",
                "state": "NY",
                "zip_code": "10001",
                "price": 2100000,
                "bedrooms": 2,
                "bathrooms": 2,
                "sq_feet": 1100,
                "property_type": "Apartment",
                "year_built": 1998,
                "description": "Luxury apartment in heart of Manhattan",
                "listed_date": "2025-02-15",
            },
            {
                "address": "789 Pine Rd",
                "city": "Austin",
                "state": "TX",
                "zip_code": "78701",
                "price": 550000,
                "bedrooms": 4,
                "bathrooms": 3,
                "sq_feet": 2500,
                "property_type": "Single Family",
                "year_built": 2015,
                "description": "Spacious home with backyard",
                "listed_date": "2025-03-10",
            },
            {
                "address": "321 Maple Dr",
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
                "price": 875000,
                "bedrooms": 3,
                "bathrooms": 2,
                "sq_feet": 1650,
                "property_type": "Townhouse",
                "year_built": 2018,
                "description": "Modern townhouse near downtown",
                "listed_date": "2025-01-20",
            },
            {
                "address": "555 Cedar Ln",
                "city": "Chicago",
                "state": "IL",
                "zip_code": "60601",
                "price": 720000,
                "bedrooms": 2,
                "bathrooms": 1.5,
                "sq_feet": 1200,
                "property_type": "Condo",
                "year_built": 2005,
                "description": "Renovated condo with lake views",
                "listed_date": "2025-02-28",
            },
        ]

        # Insert sample data
        for prop in properties:
            cursor.execute(
                """
            INSERT INTO properties 
            (address, city, state, zip_code, price, bedrooms, bathrooms, 
            sq_feet, property_type, year_built, description, listed_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    prop["address"],
                    prop["city"],
                    prop["state"],
                    prop["zip_code"],
                    prop["price"],
                    prop["bedrooms"],
                    prop["bathrooms"],
                    prop["sq_feet"],
                    prop["property_type"],
                    prop["year_built"],
                    prop["description"],
                    prop["listed_date"],
                ),
            )

        conn.commit()
        print("Sample data added to the database.")

    conn.close()


# Initialize the database
initialize_database()
populate_sample_data()

# MCP Tools for interacting with the database


@mcp.tool()
def get_all_properties() -> List[Dict]:
    """Get all properties from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM properties")
    rows = cursor.fetchall()

    properties = [dict(row) for row in rows]
    conn.close()

    return properties


@mcp.tool()
def get_property(property_id: int) -> Optional[Dict]:
    """Get a specific property by ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
    row = cursor.fetchone()

    if row:
        property_data = dict(row)
    else:
        property_data = None

    conn.close()
    return property_data


@mcp.tool()
def search_properties(
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_bedrooms: Optional[int] = None,
    property_type: Optional[str] = None,
) -> List[Dict]:
    """
    Search for properties with various filters
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM properties WHERE 1=1"
    params = []

    if city:
        query += " AND city = ?"
        params.append(city)

    if min_price is not None:
        query += " AND price >= ?"
        params.append(min_price)

    if max_price is not None:
        query += " AND price <= ?"
        params.append(max_price)

    if min_bedrooms is not None:
        query += " AND bedrooms >= ?"
        params.append(min_bedrooms)

    if property_type:
        query += " AND property_type = ?"
        params.append(property_type)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    properties = [dict(row) for row in rows]
    conn.close()

    return properties


@mcp.tool()
def add_property(
    address: str,
    city: str,
    state: str,
    zip_code: str,
    price: float,
    bedrooms: int,
    bathrooms: float,
    sq_feet: int,
    property_type: str,
    year_built: Optional[int] = None,
    description: Optional[str] = None,
) -> Dict:
    """Add a new property to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    listed_date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute(
        """
    INSERT INTO properties 
    (address, city, state, zip_code, price, bedrooms, bathrooms, 
    sq_feet, property_type, year_built, description, listed_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            address,
            city,
            state,
            zip_code,
            price,
            bedrooms,
            bathrooms,
            sq_feet,
            property_type,
            year_built,
            description,
            listed_date,
        ),
    )

    property_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"id": property_id, "message": "Property added successfully"}


@mcp.tool()
def update_property(
    property_id: int, price: Optional[float] = None, description: Optional[str] = None
) -> Dict:
    """Update price and/or description of an existing property"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if property exists
    cursor.execute("SELECT id FROM properties WHERE id = ?", (property_id,))
    if not cursor.fetchone():
        conn.close()
        return {"error": f"Property with ID {property_id} not found"}

    updates = []
    params = []

    if price is not None:
        updates.append("price = ?")
        params.append(price)

    if description is not None:
        updates.append("description = ?")
        params.append(description)

    if not updates:
        conn.close()
        return {"error": "No updates provided"}

    query = f"UPDATE properties SET {', '.join(updates)} WHERE id = ?"
    params.append(property_id)

    cursor.execute(query, params)
    conn.commit()
    conn.close()

    return {"message": f"Property {property_id} updated successfully"}


@mcp.tool()
def delete_property(property_id: int) -> Dict:
    """Delete a property from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if property exists
    cursor.execute("SELECT id FROM properties WHERE id = ?", (property_id,))
    if not cursor.fetchone():
        conn.close()
        return {"error": f"Property with ID {property_id} not found"}

    cursor.execute("DELETE FROM properties WHERE id = ?", (property_id,))
    conn.commit()
    conn.close()

    return {"message": f"Property {property_id} deleted successfully"}


@mcp.tool()
def get_statistics() -> Dict:
    """Get statistics about the real estate database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM properties")
    stats["total_properties"] = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(price) FROM properties")
    stats["average_price"] = round(cursor.fetchone()[0], 2)

    cursor.execute("SELECT MIN(price) FROM properties")
    stats["min_price"] = cursor.fetchone()[0]

    cursor.execute("SELECT MAX(price) FROM properties")
    stats["max_price"] = cursor.fetchone()[0]

    cursor.execute(
        "SELECT property_type, COUNT(*) FROM properties GROUP BY property_type"
    )
    stats["property_types"] = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("SELECT city, COUNT(*) FROM properties GROUP BY city")
    stats["cities"] = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()
    return stats


if __name__ == "__main__":
    # Start the MCP service
    mcp.run()
