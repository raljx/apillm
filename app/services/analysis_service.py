import asyncio
from typing import Any

from app.extractors.file_extractors import extract_text
from app.services.llm_client import LLMCallError, LLMClient


class AnalysisService:
    """
    Service métier principal chargé de transmettre les données extraites
    au client LLM Azure AI Foundry et de retourner le résultat.
    """

    def __init__(self) -> None:
        self.llm_client = LLMClient()

    @staticmethod
    def extract_text(
        filename: str,
        content: bytes,
    ) -> str:
        """Extrait et nettoie le texte d'un fichier reçu par l'API."""
        return extract_text(filename=filename, content=content)

    async def analyze(
        self,
        extracted_files: list[dict[str, Any]],
        additional_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyse une liste de fichiers déjà extraits sans bloquer l'event loop.

        Parameters
        ----------
        extracted_files:
            Liste des fichiers extraits par file_extractors.py.

            Exemple :
            [
                {
                    "filename": "menu.pdf",
                    "content_type": "application/pdf",
                    "text": "Contenu extrait du PDF..."
                }
            ]

        additional_context:
            Contexte optionnel envoyé au LLM.

        Returns
        -------
        dict[str, Any]
            Résultat retourné par le LLM.
        """
        if not extracted_files:
            raise ValueError("Aucun fichier à analyser.")

        normalized_files: list[dict[str, Any]] = []

        for file_data in extracted_files:
            filename = file_data.get("filename", "unknown")
            content_type = file_data.get(
                "content_type",
                "application/octet-stream",
            )
            text = file_data.get("text", "")

            if text is None:
                text = ""

            if not isinstance(text, str):
                text = str(text)

            normalized_files.append(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "text": text,
                }
            )

        try:
            return await asyncio.to_thread(
                self.llm_client.analyze,
                extracted_files=normalized_files,
                additional_context=additional_context,
            )
        except LLMCallError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Erreur lors de l'analyse des fichiers par le LLM : {exc}"
            ) from exc