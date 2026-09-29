# Menu Analyst API

API Python permettant de recevoir des fichiers de menus via une requête HTTP `POST`, d'extraire leur contenu, de construire un prompt métier et d'interroger un LLM déployé sur Azure AI Foundry / Azure OpenAI.

L'application est conçue pour être exécutée dans un conteneur puis déployée dans un pod AKS avec Helm.

## Architecture

```text
Client externe / Pod externe
            |
            | HTTP POST multipart/form-data
            v
      FastAPI / Uvicorn
            |
            v
 app/api/routes/analyze.py
            |
            v
 app/services/analysis_service.py
       |                    |
       v                    v
file_extractors.py    menu_prompt.py
       |                    |
       +---------+----------+
                 |
                 v
       app/services/llm_client.py
                 |
                 v
 Azure AI Foundry / Azure OpenAI
                 |
                 v
          Réponse JSON
```

## Arborescence

```text
menu-analyst-api/
├── app/
│   ├── main.py
│   ├── api/routes/analyze.py
│   ├── prompts/menu_prompt.py
│   └── services/
│       ├── analysis_service.py
│       ├── file_extractors.py
│       └── llm_client.py
├── charts/menu-analyst-api/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       ├── service.yaml
│       └── secret.yaml
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Créer un fichier `.env` à la racine :

```env
AZURE_OPENAI_ENDPOINT="https://VOTRE-ENDPOINT"
AZURE_OPENAI_API_KEY="VOTRE_CLE"
AZURE_OPENAI_DEPLOYMENT="gpt-5.6-sol"
```

Pour un déploiement Microsoft Foundry v1, renseigner l'endpoint Responses
complet, par exemple :

```env
AZURE_OPENAI_ENDPOINT="https://<ressource>.services.ai.azure.com/openai/v1/responses"
```

`AZURE_OPENAI_API_VERSION` n'est pas utilisé avec l'API Foundry v1 : son
versionnement est implicite. La variable peut rester dans une bibliothèque
Azure DevOps existante sans impacter l'application.

Ne jamais versionner `.env`.

Ajouter dans `.gitignore` :

```gitignore
.env
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
```

## Fonctionnement

1. Un pod externe appelle l'API avec une requête `POST`.
2. Les fichiers sont envoyés en `multipart/form-data`.
3. `file_extractors.py` extrait le texte.
4. `analysis_service.py` orchestre le traitement.
5. `menu_prompt.py` construit les instructions métier.
6. `llm_client.py` appelle Azure AI Foundry / Azure OpenAI.
7. L'API retourne la réponse du LLM en JSON.

## Installation locale Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Documentation :

```text
http://localhost:8000/docs
```

## Exécution avec Podman

### Build

```powershell
podman build --network=host -t menu-analyst-api:1.0.0 .
```

Dans l'environnement local actuel, `--network=host` permet de contourner le problème `netavark/nftables` rencontré.

### Exécution

```powershell
podman run --rm --network=host --env-file .env menu-analyst-api:1.0.0
```

## Dockerfile

À placer à la racine du projet :

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## .dockerignore

```text
.git
.gitignore
.env
.venv
venv
__pycache__
*.pyc
.pytest_cache
README.md
charts
```

## Test de l'API

Exemple avec un fichier :

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/analyze" -F "files=@C:\temp\menu.pdf"
```

Plusieurs fichiers :

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/analyze" -F "files=@C:\temp\menu1.pdf" -F "files=@C:\temp\menu2.pdf"
```

Le nom exact du champ multipart doit correspondre à celui défini dans `app/api/routes/analyze.py`.

## Rôle des fichiers

### `app/main.py`

Point d'entrée FastAPI. Il crée l'application et enregistre les routes.

### `app/api/routes/analyze.py`

Couche HTTP :

- reçoit les fichiers ;
- valide la requête ;
- appelle `AnalysisService` ;
- transforme les erreurs en réponses HTTP.

### `app/services/analysis_service.py`

Orchestrateur métier :

- appelle l'extracteur ;
- récupère le texte ;
- prépare le prompt ;
- appelle le LLM ;
- retourne le résultat.

### `app/services/file_extractors.py`

Responsable uniquement de l'extraction du contenu des fichiers entrants. La logique Azure et HTTP ne doit pas être placée dans ce fichier.

### `app/prompts/menu_prompt.py`

Contient les instructions métier du LLM et la construction du prompt.

### `app/services/llm_client.py`

Client Azure AI Foundry / Azure OpenAI.

Les imports suivants doivent rester valides :

```python
from app.services.llm_client import LLMClient
from app.services.llm_client import LLMCallError
```

## Déploiement AKS

Flux cible :

```text
Code source
   |
   v
Repository ADS
   |
   v
Pipeline CI
   |
   +--> Build image
   |
   +--> Push vers le registry interne autorisé
   |
   v
Pipeline CD
   |
   v
Helm upgrade/install
   |
   v
AKS
   |
   v
Pod menu-analyst-api
   |
   v
Azure AI Foundry / Azure OpenAI
```

## Helm

Emplacement :

```text
charts/menu-analyst-api/
```

### `Chart.yaml`

```yaml
apiVersion: v2
name: menu-analyst-api
description: Menu Analyst API
type: application
version: 0.1.0
appVersion: "1.0.0"
```

### `values.yaml`

```yaml
replicaCount: 1

image:
  repository: REPOSITORY_A_REMPLACER
  pullPolicy: IfNotPresent
  tag: "1.0.0"

imagePullSecrets: []

service:
  type: ClusterIP
  port: 8000

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: "1"
    memory: 1Gi

env:
  AZURE_OPENAI_ENDPOINT: ""
  AZURE_OPENAI_DEPLOYMENT: "gpt-5.6-terra"
  AZURE_OPENAI_API_VERSION: ""

secret:
  AZURE_OPENAI_API_KEY: ""
```

Les secrets ne doivent pas être stockés en clair dans Git.

### `templates/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "menu-analyst-api.fullname" . }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ include "menu-analyst-api.name" . }}
  template:
    metadata:
      labels:
        app: {{ include "menu-analyst-api.name" . }}
    spec:
      imagePullSecrets:
        {{- toYaml .Values.imagePullSecrets | nindent 8 }}
      containers:
        - name: menu-analyst-api
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8000
          env:
            - name: AZURE_OPENAI_ENDPOINT
              value: {{ .Values.env.AZURE_OPENAI_ENDPOINT | quote }}
            - name: AZURE_OPENAI_DEPLOYMENT
              value: {{ .Values.env.AZURE_OPENAI_DEPLOYMENT | quote }}
            - name: AZURE_OPENAI_API_VERSION
              value: {{ .Values.env.AZURE_OPENAI_API_VERSION | quote }}
            - name: AZURE_OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "menu-analyst-api.fullname" . }}-secret
                  key: AZURE_OPENAI_API_KEY
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 20
            periodSeconds: 20
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

### `templates/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "menu-analyst-api.fullname" . }}
spec:
  type: {{ .Values.service.type }}
  selector:
    app: {{ include "menu-analyst-api.name" . }}
  ports:
    - name: http
      protocol: TCP
      port: {{ .Values.service.port }}
      targetPort: http
```

### `templates/secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "menu-analyst-api.fullname" . }}-secret
type: Opaque
stringData:
  AZURE_OPENAI_API_KEY: {{ .Values.secret.AZURE_OPENAI_API_KEY | quote }}
```

### `templates/_helpers.tpl`

```gotemplate
{{- define "menu-analyst-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "menu-analyst-api.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "menu-analyst-api.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
```

## Commandes Helm

```powershell
helm lint .\charts\menu-analyst-api
helm template menu-analyst-api .\charts\menu-analyst-api
helm upgrade --install menu-analyst-api .\charts\menu-analyst-api --namespace votre-namespace --create-namespace
```

Vérifier :

```powershell
kubectl get pods -n votre-namespace
kubectl get svc -n votre-namespace
kubectl logs deployment/menu-analyst-api-menu-analyst-api -n votre-namespace
```

## Déploiement ADS

Le pipeline doit :

1. récupérer le code du dépôt ADS ;
2. construire l'image avec le `Dockerfile` ;
3. publier l'image dans Azure Container Registry (ACR), sans passer par l'Artifact Factory ;
4. déployer avec Helm vers ITG ;
5. injecter les secrets hors Git.

### Prérequis ACR

Dans Azure DevOps, créer une connexion de service de type **Docker Registry** vers
l'ACR et renseigner son nom dans `acrServiceConnection` du pipeline. Renseigner
également le *Login server* de l'ACR (par exemple
`monregistre.azurecr.io`) dans `acrLoginServer`.

L'identité managée de chacun des clusters AKS doit avoir le rôle `AcrPull` sur
l'ACR. Cette autorisation est à réaliser une fois par l'équipe Azure, par exemple :

```bash
az aks update --resource-group <groupe-ressources-aks> --name <nom-aks> --attach-acr <nom-acr>
```

Une fois ce lien en place, aucun `imagePullSecret` n'est nécessaire : Helm
déploie l'image immuable construite par le pipeline sous la forme
`<login-server>/<repository>:<Build.BuildId>`.

Vérifier le dépôt :

```powershell
git status
git branch
git remote -v
```

Si le dépôt distant contient déjà un historique :

```powershell
git pull origin main --allow-unrelated-histories
git add .
git commit -m "Merge remote repository history"
git push -u origin main
```

## Réseau AKS

Avant le déploiement ITG, vérifier avec l'équipe plateforme :

- résolution DNS ;
- règles egress ;
- firewall ;
- Private Endpoint éventuel ;
- proxy d'entreprise ;
- accès au registry ;
- accès AKS vers Azure AI Foundry / Azure OpenAI.

## Dépannage

### `ImportError: cannot import name`

Vérifier que les classes réellement importées existent, notamment :

```python
class LLMClient:
    ...

class LLMCallError(Exception):
    ...
```

Reconstruire ensuite l'image :

```powershell
podman build --network=host -t menu-analyst-api:1.0.0 .
```

### Erreur Podman `netavark` / `nftables`

Utiliser localement :

```powershell
podman build --network=host -t menu-analyst-api:1.0.0 .
podman run --rm --network=host --env-file .env menu-analyst-api:1.0.0
```

Ce contournement est spécifique au poste local et ne remplace pas la configuration réseau AKS.

### Erreur de connexion Azure

Vérifier :

- `AZURE_OPENAI_ENDPOINT` ;
- `AZURE_OPENAI_API_KEY` ;
- `AZURE_OPENAI_DEPLOYMENT` ;
- la connectivité réseau du pod ;
- les règles Azure.

## Sécurité

- Ne jamais committer `.env`.
- Ne jamais mettre de clé API dans le Dockerfile.
- Ne pas stocker les secrets en clair dans Git.
- Utiliser les secrets de la plateforme cible.
- Limiter la taille et les types de fichiers.
- Configurer des timeouts pour les appels LLM.
- Ne pas journaliser les clés ou documents sensibles.

## Checklist ITG

```text
[ ] requirements.txt présent
[ ] Dockerfile à la racine
[ ] .dockerignore présent
[ ] imports Python validés
[ ] endpoint POST testé
[ ] extraction de fichiers testée
[ ] appel Azure testé
[ ] image construite par la CI
[ ] image publiée dans le registry interne
[ ] secrets configurés hors Git
[ ] chart Helm renseigné
[ ] probes /health cohérentes avec l'application
[ ] connectivité AKS -> Azure validée
[ ] déploiement ITG validé
```

## Commandes principales

```powershell
podman build --network=host -t menu-analyst-api:1.0.0 .
podman run --rm --network=host --env-file .env menu-analyst-api:1.0.0
```

Puis :

```text
http://localhost:8000/docs
```
