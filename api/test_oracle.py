from sqlalchemy.engine.url import make_url

url = make_url("oracle+oracledb://aegon_portal:password@192.168.1.206:1521/orclpdb")
print(f"Driver: {url.drivername}")
print(f"Host: {url.host}")
print(f"Port: {url.port}")
print(f"Database (Service Name): {url.database}")
