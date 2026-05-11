from sqlmodel import Session, create_engine, select
from app.models.routine import RoutineSqlFact
from app.core.config import settings
import os

def check_facts():
    db_path = os.path.join(os.path.expanduser("~/.fastgenerate_sql_data"), "fastgenerate.db")
    if not os.path.exists(db_path):
        print("Database file not found.")
        return

    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        count = session.exec(select(RoutineSqlFact)).all()
        print(f"Total RoutineSqlFact entries: {len(count)}")
        
        if count:
            print("Sample facts:")
            for fact in count[:5]:
                print(f"- {fact.table_name} ({fact.usage_type}) in {fact.routine_id}")

if __name__ == "__main__":
    check_facts()
