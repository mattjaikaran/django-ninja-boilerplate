from api.tasks import shared_task


@shared_task
def embed_document(document_id: str) -> None:
    """Embed a document's title and body and store the vector."""
    from core.ai.models import Document
    from core.ai.services import AIClient

    document = Document.objects.get(pk=document_id)
    with AIClient.from_settings() as client:
        [vector] = client.embed([f"{document.title}\n\n{document.body}"])
    document.embedding = vector
    document.save(update_fields=["embedding", "updated_at"])
