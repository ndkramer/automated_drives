import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=127.0.0.1,1433;"
    "DATABASE=master;"
    "UID=sa;"
    "PWD=YourStrong@Passw0rd;"
)

try:
    conn = pyodbc.connect(conn_str)
    print("Connection successful!")
    conn.close()
except Exception as e:
    print("Connection failed:", e) 