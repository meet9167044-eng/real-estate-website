import mysql.connector

try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Meet12",
        database="property_db"
    )
    print("Connection successful!")
    db.close()
except mysql.connector.Error as err:
    print(f"Connection failed: {err}")


