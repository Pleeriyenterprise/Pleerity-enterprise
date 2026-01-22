"""
Storage Adapter - GridFS-based file storage with abstraction for future S3 migration.
Implements a pluggable storage interface for documents, client uploads, and deliverables.

Phase 1: MongoDB GridFS implementation
Future: S3/GCS migration via interface swap
"""
import hashlib
import io
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, BinaryIO, List
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from database import database

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class FileNotFoundError(StorageError):
    """File not found in storage."""
    pass


class FileMetadata:
    """File metadata model."""
    def __init__(
        self,
        file_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        sha256_hash: str,
        upload_timestamp: datetime,
        uploaded_by: Optional[str] = None,
        access_level: str = "private",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.file_id = file_id
        self.filename = filename
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.sha256_hash = sha256_hash
        self.upload_timestamp = upload_timestamp
        self.uploaded_by = uploaded_by
        self.access_level = access_level
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256_hash": self.sha256_hash,
            "upload_timestamp": self.upload_timestamp.isoformat() if self.upload_timestamp else None,
            "uploaded_by": self.uploaded_by,
            "access_level": self.access_level,
            "metadata": self.metadata,
        }


class StorageAdapter(ABC):
    """Abstract base class for storage implementations."""
    
    @abstractmethod
    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        uploaded_by: Optional[str] = None,
        access_level: str = "private",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Upload a file and return metadata."""
        pass
    
    @abstractmethod
    async def download_file(self, file_id: str) -> tuple[bytes, FileMetadata]:
        """Download file content and metadata."""
        pass
    
    @abstractmethod
    async def get_file_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata without downloading content."""
        pass
    
    @abstractmethod
    async def delete_file(self, file_id: str) -> bool:
        """Delete a file. Returns True if successful."""
        pass
    
    @abstractmethod
    async def file_exists(self, file_id: str) -> bool:
        """Check if a file exists."""
        pass
    
    @abstractmethod
    async def list_files(
        self,
        prefix: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[FileMetadata]:
        """List files with optional filtering."""
        pass


class GridFSStorageAdapter(StorageAdapter):
    """
    GridFS-based storage implementation.
    Stores files in MongoDB GridFS with full metadata tracking.
    """
    
    def __init__(self, bucket_name: str = "order_files"):
        self.bucket_name = bucket_name
        self._bucket = None
    
    def _get_bucket(self) -> AsyncIOMotorGridFSBucket:
        """Get or create GridFS bucket."""
        if self._bucket is None:
            db = database.get_db()
            self._bucket = AsyncIOMotorGridFSBucket(db, bucket_name=self.bucket_name)
        return self._bucket
    
    def _calculate_hash(self, data: bytes) -> str:
        """Calculate SHA256 hash of file data."""
        return hashlib.sha256(data).hexdigest()
    
    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        uploaded_by: Optional[str] = None,
        access_level: str = "private",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Upload a file to GridFS."""
        bucket = self._get_bucket()
        
        # Read file data
        if hasattr(file_data, 'read'):
            content = file_data.read()
            if isinstance(content, str):
                content = content.encode('utf-8')
        else:
            content = file_data if isinstance(file_data, bytes) else file_data.encode('utf-8')
        
        # Calculate hash
        sha256_hash = self._calculate_hash(content)
        
        # Prepare GridFS metadata
        gridfs_metadata = {
            "content_type": content_type,
            "sha256_hash": sha256_hash,
            "uploaded_by": uploaded_by,
            "access_level": access_level,
            "upload_timestamp": datetime.now(timezone.utc).isoformat(),
            "custom_metadata": metadata or {},
        }
        
        # Upload to GridFS
        file_id = await bucket.upload_from_stream(
            filename,
            io.BytesIO(content),
            metadata=gridfs_metadata,
        )
        
        file_meta = FileMetadata(
            file_id=str(file_id),
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            sha256_hash=sha256_hash,
            upload_timestamp=datetime.now(timezone.utc),
            uploaded_by=uploaded_by,
            access_level=access_level,
            metadata=metadata,
        )
        
        logger.info(f"File uploaded to GridFS: {filename} ({file_meta.file_id})")
        return file_meta
    
    async def download_file(self, file_id: str) -> tuple[bytes, FileMetadata]:
        """Download file from GridFS."""
        bucket = self._get_bucket()
        db = database.get_db()
        
        try:
            object_id = ObjectId(file_id)
        except Exception:
            raise FileNotFoundError(f"Invalid file ID: {file_id}")
        
        # Get file info first
        file_doc = await db[f"{self.bucket_name}.files"].find_one({"_id": object_id})
        if not file_doc:
            raise FileNotFoundError(f"File not found: {file_id}")
        
        # Download content
        stream = io.BytesIO()
        await bucket.download_to_stream(object_id, stream)
        content = stream.getvalue()
        
        # Build metadata
        gridfs_meta = file_doc.get("metadata", {})
        file_meta = FileMetadata(
            file_id=str(file_doc["_id"]),
            filename=file_doc["filename"],
            content_type=gridfs_meta.get("content_type", "application/octet-stream"),
            size_bytes=file_doc["length"],
            sha256_hash=gridfs_meta.get("sha256_hash", ""),
            upload_timestamp=datetime.fromisoformat(gridfs_meta.get("upload_timestamp", datetime.now(timezone.utc).isoformat())),
            uploaded_by=gridfs_meta.get("uploaded_by"),
            access_level=gridfs_meta.get("access_level", "private"),
            metadata=gridfs_meta.get("custom_metadata", {}),
        )
        
        return content, file_meta
    
    async def get_file_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata without downloading."""
        db = database.get_db()
        
        try:
            object_id = ObjectId(file_id)
        except Exception:
            return None
        
        file_doc = await db[f"{self.bucket_name}.files"].find_one({"_id": object_id})
        if not file_doc:
            return None
        
        gridfs_meta = file_doc.get("metadata", {})
        return FileMetadata(
            file_id=str(file_doc["_id"]),
            filename=file_doc["filename"],
            content_type=gridfs_meta.get("content_type", "application/octet-stream"),
            size_bytes=file_doc["length"],
            sha256_hash=gridfs_meta.get("sha256_hash", ""),
            upload_timestamp=datetime.fromisoformat(gridfs_meta.get("upload_timestamp", datetime.now(timezone.utc).isoformat())),
            uploaded_by=gridfs_meta.get("uploaded_by"),
            access_level=gridfs_meta.get("access_level", "private"),
            metadata=gridfs_meta.get("custom_metadata", {}),
        )
    
    async def delete_file(self, file_id: str) -> bool:
        """Delete file from GridFS."""
        bucket = self._get_bucket()
        
        try:
            object_id = ObjectId(file_id)
            await bucket.delete(object_id)
            logger.info(f"File deleted from GridFS: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    async def file_exists(self, file_id: str) -> bool:
        """Check if file exists in GridFS."""
        db = database.get_db()
        
        try:
            object_id = ObjectId(file_id)
            file_doc = await db[f"{self.bucket_name}.files"].find_one({"_id": object_id})
            return file_doc is not None
        except Exception:
            return False
    
    async def list_files(
        self,
        prefix: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[FileMetadata]:
        """List files with optional filtering."""
        db = database.get_db()
        
        query = {}
        if prefix:
            query["filename"] = {"$regex": f"^{prefix}"}
        if metadata_filter:
            for key, value in metadata_filter.items():
                query[f"metadata.custom_metadata.{key}"] = value
        
        cursor = db[f"{self.bucket_name}.files"].find(query).limit(limit)
        files = []
        
        async for file_doc in cursor:
            gridfs_meta = file_doc.get("metadata", {})
            files.append(FileMetadata(
                file_id=str(file_doc["_id"]),
                filename=file_doc["filename"],
                content_type=gridfs_meta.get("content_type", "application/octet-stream"),
                size_bytes=file_doc["length"],
                sha256_hash=gridfs_meta.get("sha256_hash", ""),
                upload_timestamp=datetime.fromisoformat(gridfs_meta.get("upload_timestamp", datetime.now(timezone.utc).isoformat())),
                uploaded_by=gridfs_meta.get("uploaded_by"),
                access_level=gridfs_meta.get("access_level", "private"),
                metadata=gridfs_meta.get("custom_metadata", {}),
            ))
        
        return files


# Singleton instance - GridFS for Phase 1
storage_adapter = GridFSStorageAdapter()


# Helper functions for common operations
async def upload_order_document(
    order_id: str,
    file_data: BinaryIO,
    filename: str,
    content_type: str,
    document_type: str,
    version: int,
    uploaded_by: Optional[str] = None,
) -> FileMetadata:
    """Upload a document associated with an order."""
    return await storage_adapter.upload_file(
        file_data=file_data,
        filename=f"orders/{order_id}/{filename}",
        content_type=content_type,
        uploaded_by=uploaded_by,
        access_level="private",
        metadata={
            "order_id": order_id,
            "document_type": document_type,
            "version": version,
        },
    )


async def upload_client_file(
    order_id: str,
    file_data: BinaryIO,
    filename: str,
    content_type: str,
    uploaded_by: str,
    input_version: int,
) -> FileMetadata:
    """Upload a file submitted by client."""
    return await storage_adapter.upload_file(
        file_data=file_data,
        filename=f"orders/{order_id}/client_inputs/v{input_version}/{filename}",
        content_type=content_type,
        uploaded_by=uploaded_by,
        access_level="private",
        metadata={
            "order_id": order_id,
            "source": "client_input",
            "input_version": input_version,
        },
    )


async def get_order_documents(order_id: str) -> List[FileMetadata]:
    """Get all documents for an order."""
    return await storage_adapter.list_files(
        prefix=f"orders/{order_id}/",
        metadata_filter={"order_id": order_id},
    )


async def get_file_content(file_id: str) -> io.BytesIO:
    """
    Get file content as a streaming BytesIO object.
    Used for serving documents to clients.
    """
    try:
        content, _ = await storage_adapter.download_file(file_id)
        return io.BytesIO(content)
    except Exception as e:
        logger.error(f"Failed to get file content for {file_id}: {e}")
        raise FileNotFoundError(f"File not found: {file_id}")
