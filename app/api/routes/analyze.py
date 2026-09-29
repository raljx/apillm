"""Routes HTTP pour l'analyse des fichiers de menus."""

import json
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.extractors.file_extractors import (
    FileExtractionError,
    get_file_extension,
    get_supported_extensions,
)
from app.services.analysis_service import AnalysisService
from app.services.llm_client import LLMCallError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analyse"])


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_files(
    files: list[UploadFile] = File(
        ...,
        description=(
            "Un ou plusieurs fichiers à analyser. "
            "Formats supportés : PDF, DOCX, XLSX, XLS, CSV."
        ),
    ),
):
    """Extrait puis analyse un ou plusieurs fichiers envoyés en multipart."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier reçu.",
        )

    try:
        analysis_service = AnalysisService()
    except (LLMCallError, ValueError) as exc:
        logger.error("Configuration ou initialisation LLM invalide: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service d'analyse n'est pas configuré.",
        ) from exc

    extracted_files: list[dict[str, str]] = []
    errors: list[dict[str, object]] = []

    for file in files:
        filename = file.filename or "fichier_inconnu"

        try:
            content = await file.read()
            extension = get_file_extension(filename)

            if extension not in get_supported_extensions():
                raise FileExtractionError(
                    f"Format '{extension}' non supporté. Formats acceptés : "
                    f"{', '.join(get_supported_extensions())}"
                )

            extracted_text = analysis_service.extract_text(
                filename=filename,
                content=content,
            )

            extracted_files.append(
                {
                    "filename": filename,
                    "content_type": file.content_type or "application/octet-stream",
                    "text": extracted_text,
                }
            )

        except FileExtractionError as exc:
            logger.warning("Erreur d'extraction pour '%s': %s", filename, exc)
            errors.append(
                {
                    "filename": filename,
                    "success": False,
                    "error_type": "FILE_EXTRACTION_ERROR",
                    "error": str(exc),
                }
            )

        except LLMCallError as exc:
            logger.error("Erreur LLM pour '%s': %s", filename, exc)
            errors.append(
                {
                    "filename": filename,
                    "success": False,
                    "error_type": "LLM_ERROR",
                    "error": str(exc),
                }
            )

        except Exception:
            logger.exception("Erreur inattendue pour '%s'", filename)
            errors.append(
                {
                    "filename": filename,
                    "success": False,
                    "error_type": "INTERNAL_ERROR",
                    "error": "Erreur interne lors du traitement.",
                }
            )

        finally:
            await file.close()

    if not extracted_files:
        return {
            "success": False,
            "processed_files": len(files),
            "successful_files": 0,
            "failed_files": len(errors),
            "errors": errors,
        }

    try:
        result = await analysis_service.analyze(extracted_files=extracted_files)
    except LLMCallError as exc:
        logger.error("Erreur LLM lors de l'analyse groupée: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service d'analyse n'a pas produit un JSON de menu valide.",
        ) from exc
    except Exception:
        logger.exception("Erreur inattendue lors de l'analyse groupée")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne lors de l'analyse.",
        )

    analysis_raw = result.get("analysis")
    model = result.get("model")

    try:
        analysis_json = json.loads(analysis_raw) if analysis_raw else None
    except json.JSONDecodeError as exc:
        logger.error("JSON d'analyse invalide retourné par le LLM: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service d'analyse a retourné un JSON invalide.",
        ) from exc

    return {
        "success": True,
        "processed_files": len(files),
        "successful_files": len(extracted_files),
        "failed_files": len(errors),
        "analysis": analysis_json,
        "model": model,
        "errors": errors,
    }