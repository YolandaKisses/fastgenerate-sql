from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
from typing import List, Dict, Optional
import os
from sqlmodel import Session
from app.core.config import settings
from app.core.database import get_session
from app.services import setting_service

router = APIRouter(prefix="/wiki", tags=["wiki"])

def get_wiki_root(session: Session) -> Path:
    root_str = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    return Path(root_str)

@router.get("/tree")
async def get_wiki_tree(session: Session = Depends(get_session)):
    """获取知识库目录树结构"""
    root = get_wiki_root(session)
    if not root.exists():
        return []
    
    def build_tree(path: Path) -> List[Dict]:
        tree = []
        # 按照目录优先，然后字母排序
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        for item in items:
            if item.name.startswith(".") or item.name == ".vuepress":
                continue
            
            node = {
                "name": item.name,
                "path": str(item.relative_to(root)),
                "isDir": item.is_dir()
            }
            if item.is_dir():
                node["children"] = build_tree(item)
                # 如果目录没有子节点且没有 markdown 文件，可以考虑过滤（可选）
            elif not item.suffix == ".md":
                continue
            
            tree.append(node)
        return tree

    return build_tree(root)

@router.get("/content")
async def get_wiki_content(path: str, session: Session = Depends(get_session)):
    """获取指定 Markdown 文件的内容"""
    root = get_wiki_root(session)
    file_path = (root / path).resolve()
    
    # 安全性检查：确保请求的路径在 root 目录下
    if not str(file_path).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file_path.suffix == ".md":
        raise HTTPException(status_code=400, detail="Only markdown files are supported")
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
