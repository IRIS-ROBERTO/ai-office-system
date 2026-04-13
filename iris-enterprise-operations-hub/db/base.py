import sqlalchemy
from sqlalchemy import create_engine
db_url = 'postgresql://user:password@localhost/dbname'
engine = create_engine(db_url)
Base.metadata.create_all(engine)