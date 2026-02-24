"""Document Intelligence scanner for invoice processing.

Provides helpers to scan invoice documents using Azure Document Intelligence
service.  The ``@tool`` decorator exposes ``scan_invoice`` so that the Agent
Framework can call it as a tool within a Foundry v2 agent.
"""

import json
import logging
from pathlib import Path
from typing import Annotated, Dict

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from agent_framework._tools import tool
from pydantic import Field

from app.helpers.blob_proxy import BlobStorageProxy

logger = logging.getLogger(__name__)


class DocumentIntelligenceInvoiceScanHelper:
    """Helper class for scanning invoices using Azure Document Intelligence.

    Usage:
        scanner = DocumentIntelligenceInvoiceScanHelper(client, blob_proxy)
        result = scanner.scan("path/to/invoice.pdf")
        result = scanner.scan_file(Path("local/file.pdf"))
    """

    def __init__(
        self,
        client: DocumentIntelligenceClient,
        blob_storage_proxy: BlobStorageProxy,
        model_id: str = "prebuilt-invoice",
    ) -> None:
        """Initialize the invoice scanner.

        Args:
            client: Azure Document Intelligence client
            blob_storage_proxy: Blob storage proxy for file operations
            model_id: Document Intelligence model ID (default: prebuilt-invoice)
        """
        self._client = client
        self._blob_storage_proxy = blob_storage_proxy
        self._model_id = model_id

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def scan(self, blob_name: str) -> Dict[str, str]:
        """Scan an invoice document from blob storage.

        Args:
            blob_name: Name of the blob containing the invoice document

        Returns:
            Dictionary containing extracted invoice fields
        """
        logger.info("Retrieving blob file with name [%s]", blob_name)

        blob_data = self._blob_storage_proxy.get_file_as_bytes(blob_name)
        logger.debug(
            "Found blob file with name [%s] and size [%d]",
            blob_name,
            len(blob_data),
        )
        return self._internal_scan(blob_data)

    def scan_file(self, file_path: Path) -> Dict[str, str]:
        """Scan an invoice document from a local file.

        Args:
            file_path: Path to the local invoice file

        Returns:
            Dictionary containing extracted invoice fields
        """
        with open(file_path, "rb") as fh:
            file_data = fh.read()
        return self._internal_scan(file_data)

    def _internal_scan(self, file_data: bytes) -> Dict[str, str]:
        """Internal method to scan document data.

        Args:
            file_data: Binary data of the document

        Returns:
            Dictionary containing extracted invoice fields
        """
        logger.debug("Document intelligence: start extracting data...")

        analyze_request = AnalyzeDocumentRequest(bytes_source=file_data)
        poller = self._client.begin_analyze_document(
            model_id=self._model_id,
            body=analyze_request,
        )
        result = poller.result()

        scan_data: Dict[str, str] = {}

        if result.documents:
            for document in result.documents:
                if document.fields:
                    vendor_name = document.fields.get("VendorName")
                    if vendor_name and vendor_name.value_string:
                        scan_data["VendorName"] = vendor_name.value_string

                    vendor_address = document.fields.get("VendorAddress")
                    if vendor_address and vendor_address.content:
                        scan_data["VendorAddress"] = vendor_address.content

                    customer_name = document.fields.get("CustomerName")
                    if customer_name and customer_name.value_string:
                        scan_data["CustomerName"] = customer_name.value_string

                    customer_address_recipient = document.fields.get(
                        "CustomerAddressRecipient"
                    )
                    if (
                        customer_address_recipient
                        and customer_address_recipient.value_string
                    ):
                        scan_data["CustomerAddressRecipient"] = (
                            customer_address_recipient.value_string
                        )

                    invoice_id = document.fields.get("InvoiceId")
                    if invoice_id and invoice_id.value_string:
                        scan_data["InvoiceId"] = invoice_id.value_string

                    invoice_date = document.fields.get("InvoiceDate")
                    if invoice_date and invoice_date.value_date:
                        scan_data["InvoiceDate"] = invoice_date.value_date.isoformat()

                    invoice_total = document.fields.get("InvoiceTotal")
                    if invoice_total and invoice_total.content:
                        scan_data["InvoiceTotal"] = invoice_total.content

        return scan_data

    # ------------------------------------------------------------------ #
    #  Agent Framework tool                                                #
    # ------------------------------------------------------------------ #

    @tool
    def scan_invoice(
        self,
        blob_name: Annotated[
            str,
            Field(
                description="the path to the file containing the image or photo or the attachment id"
            ),
        ],
    ) -> Annotated[
        str,
        Field(
            description=(
                "Returns a JSON string containing extracted invoice fields like "
                "VendorName, CustomerName, InvoiceId, InvoiceDate, and InvoiceTotal"
            )
        ),
    ]:
        """Function to scan invoice and bill documents and extract relevant fields."""
        try:
            scan_result = self.scan(blob_name)
            logger.debug("Scan result: %s", scan_result)
            return json.dumps(scan_result, indent=2)
        except Exception as e:
            logger.error(
                "Error scanning invoice with blob name [%s]: %s",
                blob_name,
                str(e),
            )
            return json.dumps({"error": f"Failed to scan invoice: {str(e)}"})
