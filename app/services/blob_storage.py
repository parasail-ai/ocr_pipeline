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
        container_client = self.blob_service.get_container_client(self.container_name)
        try:
            # Create container with private access (no public access)
            container_client.create_container(public_access=None)
            logger.info("Created missing blob container %s", self.container_name)
        except ResourceExistsError:
            pass

    def upload_document(self, content: bytes, filename: str, content_type: Optional[str] = None) -> tuple[str, str]:
        blob_name = f"{uuid.uuid4()}/{filename}"
        blob_client = self.blob_service.get_blob_client(container=self.container_name, blob=blob_name)
        data_stream = BytesIO(content)

        content_settings = ContentSettings(content_type=content_type or "application/octet-stream")
        blob_client.upload_blob(data_stream, overwrite=True, content_settings=content_settings)

        blob_url = blob_client.url
        return blob_name, blob_url

    def get_document_url(self, blob_path: str) -> str:
        blob_client = self.blob_service.get_blob_client(container=self.container_name, blob=blob_path)
        return blob_client.url

    def download_document(self, blob_path: str) -> bytes:
        blob_client = self.blob_service.get_blob_client(container=self.container_name, blob=blob_path)
        stream = blob_client.download_blob()
        return stream.readall()
