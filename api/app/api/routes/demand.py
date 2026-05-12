from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.models.datasource import DataSource
from app.services import demand_service, setting_service

router = APIRouter(prefix="/demand", tags=["demand"], dependencies=[Depends(get_current_user)])


class DemandFieldInput(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    original_comment: str = ""
    supplementary_comment: str = ""


class DemandRelatedTableInput(BaseModel):
    table_name: str = Field(min_length=1)
    relation_detail: str = ""


class DemandDocumentCreateRequest(BaseModel):
    datasource_id: int
    demand_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    table_comment: str = ""
    related_tables: list[DemandRelatedTableInput] = []
    fields: list[DemandFieldInput]


class DemandDocumentCreateResponse(BaseModel):
    relative_path: str
    absolute_path: str
    content: str


class DemandDocumentReadField(BaseModel):
    name: str
    type: str
    original_comment: str = ""
    supplementary_comment: str = ""


class DemandDocumentReadResponse(BaseModel):
    id: str
    name: str
    comment: str = ""
    related_tables: list[str] = []
    related_table_details: dict[str, str] = {}
    saved_path: str
    fields: list[DemandDocumentReadField] = []


class DemandCategoryNode(BaseModel):
    label: str
    key: str
    disabled: bool = False
    children: list["DemandCategoryNode"] = []


class DemandCategoryTreeResponse(BaseModel):
    tree: DemandCategoryNode
    root_key: str
    root_label: str
    default_key: str | None = None


class DemandCategoryCreateRequest(BaseModel):
    datasource_id: int
    name: str = Field(min_length=1)
    parent_path: str | None = None


class DemandCategoryRenameRequest(BaseModel):
    datasource_id: int
    path: str = Field(min_length=1)
    new_name: str = Field(min_length=1)


class DemandCategoryDeleteRequest(BaseModel):
    datasource_id: int
    path: str = Field(min_length=1)


DemandCategoryNode.model_rebuild()


def get_owned_datasource_or_404(
    session: Session,
    datasource_id: int,
    current_user,
) -> DataSource:
    datasource = session.get(DataSource, datasource_id)
    if not datasource or datasource.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="DataSource not found")
    return datasource


@router.get("/categories/{datasource_id}", response_model=DemandCategoryTreeResponse)
def read_demand_categories(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    datasource = get_owned_datasource_or_404(session, datasource_id, current_user)
    wiki_root = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    return demand_service.list_demand_categories(wiki_root, datasource.name)


@router.post("/categories", response_model=DemandCategoryNode)
def create_demand_category(
    payload: DemandCategoryCreateRequest,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user),
):
    datasource = get_owned_datasource_or_404(
        session,
        payload.datasource_id,
        current_user,
    )
    wiki_root = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    try:
        return demand_service.create_demand_category(
            wiki_root=wiki_root,
            datasource_name=datasource.name,
            name=payload.name,
            parent_path=payload.parent_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/categories", response_model=DemandCategoryNode)
def rename_demand_category(
    payload: DemandCategoryRenameRequest,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user),
):
    datasource = get_owned_datasource_or_404(
        session,
        payload.datasource_id,
        current_user,
    )
    wiki_root = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    try:
        return demand_service.rename_demand_category(
            wiki_root=wiki_root,
            datasource_name=datasource.name,
            path=payload.path,
            new_name=payload.new_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/categories")
def delete_demand_category(
    payload: DemandCategoryDeleteRequest,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user),
):
    datasource = get_owned_datasource_or_404(
        session,
        payload.datasource_id,
        current_user,
    )
    wiki_root = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    try:
        demand_service.delete_demand_category(
            wiki_root=wiki_root,
            datasource_name=datasource.name,
            path=payload.path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True}


@router.post("/documents", response_model=DemandDocumentCreateResponse)
def create_demand_document(
    payload: DemandDocumentCreateRequest,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user),
):
    datasource = get_owned_datasource_or_404(
        session,
        payload.datasource_id,
        current_user,
    )

    wiki_root = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    try:
        return demand_service.save_demand_document(
            wiki_root=wiki_root,
            datasource_name=datasource.name,
            demand_name=payload.demand_name,
            table_name=payload.table_name,
            table_comment=payload.table_comment,
            related_tables=[item.model_dump() for item in payload.related_tables],
            fields=[field.model_dump() for field in payload.fields],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents/{datasource_id}", response_model=list[DemandDocumentReadResponse])
def read_demand_documents(
    datasource_id: int,
    demand_name: str,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user),
):
    datasource = get_owned_datasource_or_404(session, datasource_id, current_user)
    wiki_root = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    try:
        return demand_service.list_demand_documents(
            wiki_root=wiki_root,
            datasource_name=datasource.name,
            demand_name=demand_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
