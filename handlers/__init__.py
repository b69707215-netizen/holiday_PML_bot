from handlers.common import router as common_router
from handlers.teacher import router as teacher_router
from handlers.secretary import router as secretary_router
from handlers.crm import router as crm_router
from handlers.document_upload import router as document_upload_router

__all__ = ["common_router", "teacher_router", "secretary_router", "crm_router", "document_upload_router"]
