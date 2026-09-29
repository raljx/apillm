import json
import os
from typing import Any

from openai import OpenAI

from app.prompts.menu_prompt import SYSTEM_PROMPT
from app.services.menu_merger import merge_menu_payloads


class LLMCallError(Exception):
    """Exception levée lorsqu'un appel au LLM Azure OpenAI échoue."""


class LLMClient:
    """Client chargé de communiquer avec Azure OpenAI / Azure AI Foundry."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

        missing_variables = []

        if not self.endpoint:
            missing_variables.append("AZURE_OPENAI_ENDPOINT")

        if not self.api_key:
            missing_variables.append("AZURE_OPENAI_API_KEY")

        if not self.deployment_name:
            missing_variables.append("AZURE_OPENAI_DEPLOYMENT")

        if missing_variables:
            raise LLMCallError(
                "Variables d'environnement Azure OpenAI manquantes ou vides : "
                + ", ".join(missing_variables)
            )

        try:
            self.client = OpenAI(
                base_url=self._get_foundry_base_url(self.endpoint),
                api_key=self.api_key,
            )
        except Exception as exc:
            raise LLMCallError(
                f"Impossible d'initialiser le client Azure OpenAI : {exc}"
            ) from exc

    def analyze(
        self,
        extracted_files: list[dict[str, Any]],
        additional_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyse chaque fichier indépendamment, puis fusionne les JSON en Python.

        Le LLM extrait les informations ; le mergeur garantit l'unicité des dates,
        des tranches d'âge et les règles d'union métier.
        """
        if not extracted_files:
            raise LLMCallError("Aucun fichier exploitable à analyser.")

        try:
            payloads: list[dict[str, Any]] = []
            model_name = self.deployment_name

            for index, file_data in enumerate(extracted_files, start=1):
                filename = file_data.get("filename", f"fichier_{index}")
                content_type = file_data.get(
                    "content_type",
                    "application/octet-stream",
                )
                text = file_data.get("text") or ""

                payload, response_model = self._analyze_one_file(
                    filename=filename,
                    content_type=content_type,
                    text=str(text),
                    additional_context=additional_context,
                )

                payloads.append(payload)
                model_name = response_model or model_name

            merged_content = merge_menu_payloads(payloads)

            return {
                "analysis": json.dumps(
                    merged_content,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
                "model": model_name,
            }

        except LLMCallError:
            raise
        except (TypeError, ValueError) as exc:
            raise LLMCallError(
                f"Le JSON de menu retourné ne respecte pas le format attendu : {exc}"
            ) from exc
        except Exception as exc:
            raise LLMCallError(
                f"Erreur lors de l'appel au LLM Azure OpenAI : {exc}"
            ) from exc

    def _analyze_one_file(
        self,
        filename: str,
        content_type: str,
        text: str,
        additional_context: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Appelle le LLM pour un seul document."""
        files_content = self._build_files_content(
            [
                {
                    "filename": filename,
                    "content_type": content_type,
                    "text": text,
                }
            ]
        )

        user_prompt = self._build_user_prompt(
            files_content=files_content,
            additional_context=additional_context,
        )

        try:
            response = self.client.responses.create(
                model=self.deployment_name,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
            )

            content = response.output_text

            if not content:
                raise LLMCallError(
                    f"Le LLM Azure OpenAI n'a retourné aucun contenu pour "
                    f"'{filename}'."
                )

            try:
                parsed_content = json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMCallError(
                    f"Le LLM n'a pas produit un JSON valide pour "
                    f"'{filename}' : {exc}"
                ) from exc

            if not isinstance(parsed_content, dict):
                raise LLMCallError(
                    f"Le JSON retourné pour '{filename}' doit être un objet."
                )

            return parsed_content, getattr(response, "model", None)

        except LLMCallError:
            raise
        except Exception as exc:
            raise LLMCallError(
                f"Erreur lors de l'analyse du fichier '{filename}' : {exc}"
            ) from exc

    @staticmethod
    def _get_foundry_base_url(endpoint: str) -> str:
        """Normalise l'endpoint Foundry Responses en URL de base du SDK."""
        base_url = endpoint.rstrip("/")

        if base_url.endswith("/responses"):
            base_url = base_url.removesuffix("/responses")

        if not base_url.endswith("/openai/v1"):
            raise LLMCallError(
                "AZURE_OPENAI_ENDPOINT doit être l'endpoint Foundry v1, "
                "par exemple "
                "'https://<ressource>.services.ai.azure.com/"
                "openai/v1/responses'."
            )

        return f"{base_url}/"

    @staticmethod
    def _build_files_content(
        extracted_files: list[dict[str, Any]],
    ) -> str:
        """Prépare les contenus des fichiers pour le prompt."""
        parts: list[str] = []

        for index, file_data in enumerate(extracted_files, start=1):
            filename = file_data.get("filename", f"fichier_{index}")
            content_type = file_data.get(
                "content_type",
                "application/octet-stream",
            )
            text = file_data.get("text") or ""

            if not isinstance(text, str):
                text = str(text)

            parts.append(
                f"""--- FICHIER {index} ---
Nom : {filename}
Type : {content_type}

Contenu :
{text}
--- FIN FICHIER {index} ---"""
            )

        return "\n\n".join(parts)

    @staticmethod
    def _build_user_prompt(
        files_content: str,
        additional_context: str | None = None,
    ) -> str:
        """Construit le message utilisateur envoyé au modèle."""
        context = ""

        if additional_context:
            context = f"""CONTEXTE ADDITIONNEL :
{additional_context}
"""

        return f"""Analyse le document fourni conformément aux instructions système.

{context}
DOCUMENT À ANALYSER :

{files_content}
"""