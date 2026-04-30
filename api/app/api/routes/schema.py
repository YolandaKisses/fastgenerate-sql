from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.models.datasource import DataSource
from app.models.schema import SchemaTable, SchemaField
from app.services import schema_service
from pydantic import BaseModel

router = APIRouter(prefix="/schema", tags=["schema"])

class RemarkUpdate(BaseModel):
    remark: str

@router.post("/sync/{datasource_id}")
def sync_schema(datasource_id: int, session: Session = Depends(get_session)):
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"success": False, "message": "DataSource not found"}
    return schema_service.sync_schema_for_datasource(session, ds)

@router.get("/tables/{datasource_id}", response_model=list[SchemaTable])
def read_tables(datasource_id: int, session: Session = Depends(get_session)):
    return schema_service.get_tables(session, datasource_id)

@router.patch("/tables/{table_id}/remark", response_model=SchemaTable)
def update_table_remark(table_id: int, remark_data: RemarkUpdate, session: Session = Depends(get_session)):
    return schema_service.update_table_remark(session, table_id, remark_data.remark)

@router.get("/fields/{table_id}", response_model=list[SchemaField])
def read_fields(table_id: int, session: Session = Depends(get_session)):
    return schema_service.get_fields(session, table_id)

@router.patch("/fields/{field_id}/remark", response_model=SchemaField)
def update_field_remark(field_id: int, remark_data: RemarkUpdate, session: Session = Depends(get_session)):
    return schema_service.update_field_remark(session, field_id, remark_data.remark)
