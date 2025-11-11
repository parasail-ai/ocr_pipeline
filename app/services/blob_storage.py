import logging
import uuid
from io import BytesIO
from typing import Optional

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BlobStorageService:
    """Wrapper around Azure Blob Storage for document management."""

    def __init__(self, connection_string: Optional[str] = None, container_name: Optional[str] = None) -> None:
        settings = get_settings()

        self.container_name = container_name or settings.azure_blob_container
        connection_string = connection_string or settings.azure_storage_connection_string

        if connection_string:
            self.blob_service = BlobServiceClient.from_connection_string(connection_string)
        elif settings.azure_storage_account_url:
            credential = DefaultAzureCredential()
            self.blob_service = BlobServiceClient(account_url=str(settings.azure_storage_account_url), credential=credential)
        else:
            raise RuntimeError("Azure storage configuration is missing. Provide a connection string or account URL.")

        self._ensure_container()

    def _ensure_container(self) -> None:
        """Ensure the container exists. If it already exists, this is a no-op."""
        container_client = self.blob_service.get_container_client(self.container_name)
        try:
            # Check if container exists first
            container_client.get_container_properties()
            logger.info("Container %s already exists", self.container_name)
        except Exception:
            # Container doesn't exist, create it with private access
            try:
                container_client.create_container(public_access=None)
                logger.info("Created container %s with private access", self.container_name)
            except Exception as e:
                logger.error("Failed to create container %s: %s", self.container_name, str(e))
                raise

    def upload_document(self, content: bytes, filename: str, content_type: Optional[str] = None) -> tuple[str, str]:
        # URL-encode the filename to handle spaces and special characters
        from urllib.parse import quote
        safe_filename = quote(filename, safe='')
        
        blob_name = f"{uuid.uuid4()}/{safe_filename}"
        blob_client = self.blob_service.get_blob_client(container=self.container_name, blob=blob_name)
        data_stream = BytesIO(content)

        content_settings = ContentSettings(content_type=content_type or "application/octet-stream")
        blob_client.upload_blob(data_stream, overwrite=True, content_settings=content_settings)

        # Return the blob path and a placeholder URL (actual access will be through authenticated methods)
        # blob_client.url can fail when public access is not permitted
        blob_url = f"https://{self.blob_service.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"
        return blob_name, blob_url

    def get_document_url(self, blob_path: str) -> str:
        blob_client = self.blob_service.get_blob_client(container=self.container_name, blob=blob_path)
        return blob_client.url

    def download_document(self, blob_path: str) -> bytes:
        blob_client = self.blob_service.get_blob_client(container=self.container_name, blob=blob_path)
        stream = blob_client.download_blob()
        return stream.readall()

    def delete_document(self, blob_path: str) -> None:
        """Delete a document from blob storage."""
        blob_client = self.blob_service.get_blob_client(container=self.container_name, blob=blob_path)
        try:
            blob_client.delete_blob()
            logger.info("Deleted blob %s from container %s", blob_path, self.container_name)
        except Exception as e:
            logger.error("Failed to delete blob %s: %s", blob_path, str(e))
            raise
