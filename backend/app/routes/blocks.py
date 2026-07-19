from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.block import BlockCreate, BlockRead
from ..services.auth import require_admin
from ..services.schedule import create_block, delete_block

router = APIRouter(prefix="/blocks", tags=["blocks"], dependencies=[Depends(require_admin)])


@router.post("", response_model=BlockRead, status_code=201)
def block_slot(payload: BlockCreate, db: Session = Depends(get_db)):
    block = create_block(db, payload)
    return BlockRead(id=block.id, date=block.date, start_time=block.start_time, reason=block.reason)


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_slot(block_id: int, db: Session = Depends(get_db)):
    delete_block(db, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
