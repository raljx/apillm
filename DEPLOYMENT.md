# Documentation de déploiement — menu-analyst-api

## 1. Objet

Ce document décrit la méthode de déploiement de `menu-analyst-api` sur les environnements **ITG**, **PRP** et **PROD**.

La solution est une API Python/FastAPI déployée dans AKS. L'image Docker est construite par Azure DevOps et publiée dans Azure Container Registry (ACR), puis le chart Helm déploie cette image dans le namespace Kubernetes correspondant.

Le pipeline fourni dans `azure-pipelines(5).yml` met en œuvre le flux suivant :

```text
                     Azure DevOps
                          |
                          v
                    +-----------+
                    | Validate  |
                    +-----------+
                          |
                          v
                  +---------------+
                  | BuildImage    |
                  | Docker build  |
                  | Docker push   |
                  +---------------+
                          |
                          v
             +--------------------------+
             | Environnement sélectionné|
             +--------------------------+
                 /          |          \
                /           |           \
               v            v            v
            ITG            PRP          PROD
             |              |             |
             v              v             v
            AKS            AKS           AKS
```

---

# 2. Structure du projet

La structure attendue par le pipeline est :

```text
menu-analyst-api/
│
├── Dockerfile
├── requirements.txt
│
├── app/
│   ├── main.py
│   ├── api/
│   ├── services/
│   ├── prompts/
│   └── ...
│
├── helm/
│   └── menu-analyst-api/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-itg.yaml
│       ├── values-prp.yaml
│       ├── values-prod.yaml
│       │
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── ingress.yaml
│           ├── configmap.yaml
│           ├── secret.yaml
│           ├── hpa.yaml
│           └── serviceaccount.yaml
│
└── azure-pipelines.yml
```

Le pipeline vérifie explicitement l'existence de :

```text
Dockerfile
requirements.txt
app/main.py
helm/menu-analyst-api/Chart.yaml
helm/menu-analyst-api/values.yaml
helm/menu-analyst-api/values-itg.yaml
helm/menu-analyst-api/values-prp.yaml
helm/menu-analyst-api/values-prod.yaml
```

---

# 3. Principe de déploiement

Le déploiement est volontairement séparé en deux grandes phases :

1. **Construction et publication de l'image**
2. **Déploiement Kubernetes**

Le pipeline ne construit pas une image différente pour chaque environnement.

Le mécanisme actuel utilise en revanche un repository ACR différent selon l'environnement sélectionné.

| Environnement | Repository ACR | Namespace AKS | Values Helm |
|---|---|---|---|
| ITG | `monaco-city-itg-services-api-menu-analyst` | `monaco-city-itg` | `values-itg.yaml` |
| PRP | `monaco-city-prp-services-api-menu-analyst` | `monaco-city-prp` | `values-prp.yaml` |
| PROD | `monaco-city-prod-services-api-menu-analyst` | `monaco-city-prod` | `values-prod.yaml` |

Le tag de l'image est :

```text
$(Build.BuildId)
```

Ce tag est immuable pour un build donné et permet de retrouver précisément l'image déployée.

---

# 4. Paramètre d'environnement

Le pipeline définit le paramètre :

```yaml
parameters:
  - name: targetEnvironment
    displayName: "Environnement cible"
    type: string
    default: itg
    values:
      - itg
      - prp
      - prod
```

Lors du lancement manuel du pipeline, Azure DevOps propose :

```text
Environnement cible
    ITG
    PRP
    PROD
```

Le choix détermine le stage de déploiement exécuté.

Les stages sont :

```text
Validate
BuildImage
DeployITG
DeployPRP
DeployPROD
```

Les trois stages de déploiement sont mutuellement exclusifs grâce aux conditions :

```yaml
condition: and(succeeded(), eq('${{ parameters.targetEnvironment }}', 'itg'))
```

```yaml
condition: and(succeeded(), eq('${{ parameters.targetEnvironment }}', 'prp'))
```

```yaml
condition: and(succeeded(), eq('${{ parameters.targetEnvironment }}', 'prod'))
```

---

# 5. Pré-requis Azure DevOps

## 5.1 Agent

Le pipeline utilise :

```yaml
pool:
  name: "ads_Linux_Proxyfied"
```

L'agent doit disposer au minimum de :

```text
Docker
Azure CLI
kubectl
Helm
Bash
```

Vérification :

```bash
docker --version
az --version
kubectl version --client
helm version
```

---

# 6. Service Connections

Deux types de connexions sont utilisés.

## 6.1 Connexion Docker Registry

Le build utilise :

```yaml
- task: Docker@2
  inputs:
    command: "buildAndPush"
    containerRegistry: "$(acrServiceConnection)"
```

La variable actuelle est :

```yaml
acrServiceConnection: "AzureYourMonacoDockerRegistry"
```

Cette connexion doit impérativement être de type :

```text
Docker Registry
```

Elle ne doit pas être une connexion :

```text
Azure Resource Manager
```

Une connexion AKS de type `azurerm` ne peut pas être passée à `Docker@2.containerRegistry`.

---

## 6.2 Connexions Azure Resource Manager pour AKS

ITG utilise :

```yaml
azureSubscription: "ServiceConnection-AKS-ITG"
```

PRP utilise :

```yaml
azureSubscription: "ServiceConnection-AKS-PRP"
```

PROD utilise :

```yaml
azureSubscription: "sp-tf-sub-monaco-prod-001"
```

Ces connexions sont de type :

```text
Azure Resource Manager
```

Elles servent à exécuter :

```bash
az aks get-credentials
```

et à récupérer un kubeconfig temporaire permettant ensuite à `kubectl` et `helm` de communiquer avec AKS.

---

# 7. Variable Group

Le pipeline charge :

```yaml
- group: menu-analyst-aks
```

Le Variable Group doit donc exister dans Azure DevOps.

Il doit notamment contenir les paramètres nécessaires à la connexion aux clusters :

```text
aksResourceGroupITG
aksClusterNameITG

aksResourceGroupPRP
aksClusterNamePRP

aksResourceGroupPROD
aksClusterNamePROD
```

Il contient également les paramètres Azure OpenAI utilisés par Helm :

```text
azureOpenAIEndpoint
azureOpenAIDeployment
azureOpenAIApiVersion
azureOpenAIApiKey
```

La clé API doit être configurée comme variable secrète.

---

# 8. Azure Container Registry

Le pipeline utilise actuellement :

```yaml
acrLoginServer: "crfrcyourmonacomcocityplt001.azurecr.io"
```

Les repositories sont sélectionnés en fonction de l'environnement.

## ITG

```text
crfrcyourmonacomcocityplt001.azurecr.io/monaco-city-itg-services-api-menu-analyst
```

## PRP

```text
crfrcyourmonacomcocityplt001.azurecr.io/monaco-city-prp-services-api-menu-analyst
```

## PROD

```text
crfrcyourmonacomcocityplt001.azurecr.io/monaco-city-prod-services-api-menu-analyst
```

Le tag est :

```text
$(Build.BuildId)
```

Exemple :

```text
crfrcyourmonacomcocityplt001.azurecr.io/monaco-city-itg-services-api-menu-analyst:12345
```

---

# 9. Accès AKS à l'ACR

Le pipeline pousse l'image dans ACR.

Mais ce n'est pas suffisant.

Les nodes / identités utilisés par AKS doivent pouvoir récupérer l'image.

L'identité AKS doit disposer du rôle Azure :

```text
AcrPull
```

sur l'ACR concerné.

À vérifier avant le premier déploiement :

```bash
az aks show \
  --resource-group <RESOURCE_GROUP> \
  --name <AKS_CLUSTER> \
  --query identity
```

Puis vérifier les permissions ACR.

En cas de :

```text
ImagePullBackOff
```

ou :

```text
ErrImagePull
```

vérifier en priorité :

```bash
kubectl describe pod <POD> -n <NAMESPACE>
```

et les permissions `AcrPull`.

---

# 10. Stage Validate

Le premier stage est :

```text
Validate
```

Il vérifie la structure du projet.

Le pipeline exécute notamment :

```bash
find . -maxdepth 5 -type f -print | sort
```

puis vérifie les fichiers nécessaires.

Ensuite Helm est validé :

```bash
helm lint helm/menu-analyst-api
```

Pour chaque environnement :

```text
values-itg.yaml
values-prp.yaml
values-prod.yaml
```

le pipeline réalise :

```bash
helm lint
```

puis :

```bash
helm template
```

Cette étape permet de détecter les erreurs Helm avant tout déploiement.

---

# 11. Stage BuildImage

Le stage :

```text
BuildImage
```

dépend de :

```text
Validate
```

Il est exécuté avant les stages AKS.

La construction utilise :

```yaml
Docker@2
```

avec :

```yaml
command: "buildAndPush"
```

Le Dockerfile utilisé est :

```text
$(Build.SourcesDirectory)/Dockerfile
```

Le contexte de build est :

```text
$(Build.SourcesDirectory)
```

Les deux tags produits sont :

```text
$(Build.BuildId)
latest
```

L'image immuable à déployer est :

```text
$(Build.BuildId)
```

Le pipeline affiche ensuite :

```text
Image publiée :
<ACR>/<repository>:<BuildId>
```

---

# 12. Déploiement ITG

## 12.1 Connexion AKS

Le pipeline utilise :

```yaml
azureSubscription: "ServiceConnection-AKS-ITG"
```

Puis :

```bash
az aks get-credentials \
  --resource-group "${AKS_RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER_NAME}" \
  --file "${KUBECONFIG_FILE}" \
  --overwrite-existing
```

Le kubeconfig est stocké dans :

```text
$(Pipeline.Workspace)/kubeconfig-itg
```

avec des permissions :

```text
600
```

---

## 12.2 Namespace

Le namespace cible est :

```text
monaco-city-itg
```

Le pipeline vérifie son existence :

```bash
kubectl get namespace monaco-city-itg
```

et le crée si nécessaire.

---

## 12.3 Secret Azure OpenAI

La variable :

```text
azureOpenAIApiKey
```

est écrite dans un fichier temporaire protégé.

Le fichier est ensuite injecté à Helm avec :

```bash
--set-file secret.azureOpenAIApiKey="$(azureOpenAIApiKeyFile)"
```

La clé n'est donc pas directement écrite dans le dépôt Git.

Le template Helm `secret.yaml` produit :

```yaml
kind: Secret
```

avec :

```yaml
AZURE_OPENAI_API_KEY
```

---

# 13. Déploiement Helm

Le chart utilisé est :

```text
helm/menu-analyst-api
```

Les valeurs de base sont chargées avec :

```text
values.yaml
```

puis les valeurs spécifiques à l'environnement :

```text
values-itg.yaml
```

Le pipeline surcharge notamment :

```text
fullnameOverride
image.repository
image.tag
azureOpenAIEndpoint
azureOpenAIDeployment
azureOpenAIApiVersion
azureOpenAIApiKey
```

Exemple :

```bash
helm upgrade \
  --install \
  menu-analyst-api-release \
  helm/menu-analyst-api \
  --namespace monaco-city-itg \
  --create-namespace \
  -f helm/menu-analyst-api/values.yaml \
  -f helm/menu-analyst-api/values-itg.yaml \
  --set fullnameOverride="$(workloadName)" \
  --set image.repository="$(acrLoginServer)/$(acrRepository)" \
  --set image.tag="$(imageTag)" \
  --wait \
  --timeout 10m \
  --atomic
```

L'option :

```text
--atomic
```

permet de revenir à l'état précédent si le déploiement échoue.

---

# 14. Ressources Kubernetes déployées

Le chart contient les ressources suivantes.

## Deployment

Fichier :

```text
templates/deployment.yaml
```

Il crée le Pod applicatif.

L'image est :

```yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
```

Le port applicatif est nommé :

```yaml
ports:
  - name: http
    containerPort: {{ .Values.containerPort }}
```

Le nom `http` est important car le Service utilise :

```yaml
targetPort: http
```

---

# 15. Health checks

Le Deployment utilise deux probes.

## Liveness

```yaml
livenessProbe:
  httpGet:
    path: {{ .Values.livenessProbe.path }}
    port: http
```

Elle permet à Kubernetes de déterminer si le processus doit être redémarré.

## Readiness

```yaml
readinessProbe:
  httpGet:
    path: {{ .Values.readinessProbe.path }}
    port: http
```

Elle permet de déterminer si le Pod peut recevoir du trafic.

La route configurée dans les valeurs Helm doit donc exister réellement dans FastAPI.

---

# 16. Service Kubernetes

Fichier :

```text
templates/service.yaml
```

Le Service est :

```yaml
kind: Service
```

Le type est contrôlé par :

```yaml
.Values.service.type
```

Le port est :

```yaml
port: {{ .Values.service.port }}
```

Le `targetPort` est :

```yaml
targetPort: http
```

Le Service sélectionne les Pods via :

```yaml
selector:
  {{- include "menu-analyst-api.selectorLabels" . | nindent 4 }}
```

Il est donc indispensable que les labels du Deployment et le selector du Service correspondent.

---

# 17. Communication interne entre Pods

Depuis un autre Pod du même namespace, l'appel doit utiliser le nom du Service Kubernetes.

Le nom réel est :

```text
{{ include "menu-analyst-api.fullname" . }}
```

Avec le `fullnameOverride` du pipeline, il correspond au `workloadName` de l'environnement.

Pour ITG, le pipeline utilise :

```text
monaco-city-itg-services-api-menu-analyst
```

Il faut donc tester :

```bash
curl -v \
  http://monaco-city-itg-services-api-menu-analyst:8000/health
```

ou le FQDN Kubernetes :

```bash
curl -v \
  http://monaco-city-itg-services-api-menu-analyst.monaco-city-itg.svc.cluster.local:8000/health
```

Ne pas supposer que le nom de la release Helm est automatiquement le nom du Service.

---

# 18. Diagnostic Service → Pod

En cas de problème de communication :

```bash
kubectl get svc -n monaco-city-itg
```

Puis :

```bash
kubectl get endpoints -n monaco-city-itg
```

Le Service doit posséder au moins un endpoint.

Exemple attendu :

```text
NAME                                      ENDPOINTS
monaco-city-itg-services-api-menu-analyst  10.10.2.47:8000
```

Si :

```text
ENDPOINTS   <none>
```

le Service ne sélectionne aucun Pod.

Comparer alors :

```bash
kubectl get svc <SERVICE> \
  -n monaco-city-itg \
  -o yaml
```

avec :

```bash
kubectl get pods \
  -n monaco-city-itg \
  --show-labels
```

---

# 19. API HTTP

L'endpoint d'analyse est appelé en POST lorsque des fichiers sont transmis.

Un appel GET comme :

```bash
curl \
  "http://<SERVICE>:8000/api/v1/analyze"
```

n'est pas équivalent à l'appel d'analyse avec upload.

Le test doit respecter le contrat de l'API.

Pour un endpoint multipart, le principe est :

```bash
curl -v \
  -X POST \
  http://<SERVICE>:8000/api/v1/analyze \
  -F "file=@menu.pdf"
```

Le nom exact du champ multipart doit correspondre à celui défini dans le code FastAPI.

---

# 20. Ingress

Fichier :

```text
templates/ingress.yaml
```

L'Ingress est conditionnel :

```yaml
{{- if .Values.ingress.enabled }}
```

Il n'est donc créé que si :

```text
ingress.enabled=true
```

Le backend de l'Ingress pointe vers le Service :

```yaml
service:
  name: {{ include "menu-analyst-api.fullname" $ }}
```

et vers :

```text
.Values.service.port
```

Les hosts et TLS sont fournis par les valeurs Helm de l'environnement.

Vérification :

```bash
kubectl get ingress -n monaco-city-itg
```

Puis :

```bash
kubectl describe ingress <INGRESS> -n monaco-city-itg
```

---

# 21. ConfigMap

Fichier :

```text
templates/configmap.yaml
```

Le ConfigMap contient :

```text
LOG_LEVEL
MAX_UPLOAD_SIZE_MB
```

avec les valeurs :

```text
.Values.config.logLevel
.Values.config.maxUploadSizeMb
```

Le template `deployment.yaml` fourni injecte directement les variables Azure OpenAI et la clé via Secret.

Il faut vérifier dans le chart complet que les valeurs du ConfigMap sont effectivement consommées par le Deployment. Le fichier `configmap.yaml` seul ne suffit pas à injecter automatiquement ses valeurs dans le conteneur.

---

# 22. Secret

Fichier :

```text
templates/secret.yaml
```

Le Secret contient :

```text
AZURE_OPENAI_API_KEY
```

Le Deployment récupère cette valeur avec :

```yaml
valueFrom:
  secretKeyRef:
    name: {{ include "menu-analyst-api.fullname" . }}-secret
    key: AZURE_OPENAI_API_KEY
```

Il est recommandé de ne jamais committer une clé réelle dans :

```text
values.yaml
values-itg.yaml
values-prp.yaml
values-prod.yaml
```

La valeur doit provenir du Variable Group Azure DevOps ou d'un mécanisme de secrets dédié.

---

# 23. ServiceAccount

Fichier :

```text
templates/serviceaccount.yaml
```

Le ServiceAccount est conditionnel :

```yaml
{{- if .Values.serviceAccount.create }}
```

Le template crée le compte avec :

```text
menu-analyst-api.serviceAccountName
```

Le Deployment fourni doit être vérifié pour confirmer que le champ :

```yaml
serviceAccountName:
```

est bien configuré si un ServiceAccount spécifique est nécessaire.

À défaut, Kubernetes utilisera le ServiceAccount `default`.

---

# 24. HPA

Fichier :

```text
templates/hpa.yaml
```

Le HPA est créé uniquement lorsque :

```text
.Values.autoscaling.enabled
```

est activé.

Il cible :

```yaml
kind: Deployment
name: {{ include "menu-analyst-api.fullname" . }}
```

Le scaling est basé sur le CPU :

```yaml
type: Resource
resource:
  name: cpu
```

avec :

```text
averageUtilization
```

Le cluster doit disposer des métriques nécessaires pour que le HPA puisse fonctionner correctement.

Vérification :

```bash
kubectl get hpa -n monaco-city-itg
```

Puis :

```bash
kubectl describe hpa <HPA> -n monaco-city-itg
```

---

# 25. Vérification post-déploiement

Après Helm :

```bash
helm status menu-analyst-api-release \
  -n monaco-city-itg
```

Puis :

```bash
kubectl get deployment \
  -n monaco-city-itg \
  -o wide \
  --show-labels
```

Puis :

```bash
kubectl get pods \
  -n monaco-city-itg \
  -o wide \
  --show-labels
```

Puis :

```bash
kubectl get svc \
  -n monaco-city-itg \
  -o wide
```

Puis :

```bash
kubectl get ingress \
  -n monaco-city-itg \
  -o wide
```

Enfin :

```bash
kubectl get events \
  -n monaco-city-itg \
  --sort-by=.metadata.creationTimestamp
```

---

# 26. Logs applicatifs

Récupérer les Pods :

```bash
kubectl get pods -n monaco-city-itg
```

Puis :

```bash
kubectl logs \
  <POD> \
  -n monaco-city-itg \
  --all-containers=true \
  --tail=200
```

En cas de crash précédent :

```bash
kubectl logs \
  <POD> \
  -n monaco-city-itg \
  --all-containers=true \
  --previous \
  --tail=200
```

Pour les événements et erreurs Kubernetes :

```bash
kubectl describe pod \
  <POD> \
  -n monaco-city-itg
```

---

# 27. Diagnostic d'un Pod qui ne démarre pas

## Image introuvable

```text
ErrImagePull
ImagePullBackOff
```

Vérifier :

```bash
kubectl describe pod <POD> -n <NAMESPACE>
```

Puis :

```text
ACR
repository
tag
AcrPull
imagePullSecrets
```

---

## Container qui démarre puis s'arrête

Vérifier :

```bash
kubectl logs <POD> -n <NAMESPACE>
```

et :

```bash
kubectl logs <POD> -n <NAMESPACE> --previous
```

Puis :

```bash
kubectl describe pod <POD> -n <NAMESPACE>
```

---

## Readiness probe en échec

Vérifier que l'API écoute sur :

```text
0.0.0.0:<PORT>
```

et non :

```text
127.0.0.1:<PORT>
```

Le container doit démarrer Uvicorn avec un bind compatible Kubernetes, par exemple :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Vérifier également que la route de readiness définie dans les values existe réellement.

---

# 28. Déploiement PRP

Le principe est identique à ITG.

Namespace :

```text
monaco-city-prp
```

Values :

```text
values-prp.yaml
```

Connexion Azure :

```text
ServiceConnection-AKS-PRP
```

Variables AKS :

```text
aksResourceGroupPRP
aksClusterNamePRP
```

Repository :

```text
monaco-city-prp-services-api-menu-analyst
```

---

# 29. Déploiement PROD

Le principe est identique à ITG et PRP.

Namespace :

```text
monaco-city-prod
```

Values :

```text
values-prod.yaml
```

Connexion Azure :

```text
sp-tf-sub-monaco-prod-001
```

Variables AKS :

```text
aksResourceGroupPROD
aksClusterNamePROD
```

Repository :

```text
monaco-city-prod-services-api-menu-analyst
```

La branche autorisée pour PROD doit être maîtrisée au niveau des règles Azure DevOps et des politiques du repository. Le pipeline actuel déclenche sur `main`, `release/*`, `feature/*` et `bugfix/*`; le contrôle métier de la promotion PROD doit donc être complété par les règles d'environnement/approbations ADS si nécessaire.

---

# 30. Procédure complète ITG

## Étape 1 — Commit

```bash
git status
git add .
git commit -m "Deploy menu-analyst-api"
git push
```

## Étape 2 — Lancer le pipeline

Dans Azure DevOps :

```text
Pipelines
→ menu-analyst-api
→ Run pipeline
```

Sélectionner :

```text
Environnement cible = itg
```

## Étape 3 — Validate

Vérifier :

```text
Contrôle structure projet
Validation Helm
```

## Étape 4 — BuildImage

Vérifier :

```text
Docker build
Docker push
```

L'image doit être disponible dans :

```text
crfrcyourmonacomcocityplt001.azurecr.io/
monaco-city-itg-services-api-menu-analyst:
<BuildId>
```

## Étape 5 — DeployITG

Le pipeline :

```text
récupère les credentials AKS
    ↓
prépare le Secret Azure OpenAI
    ↓
valide Helm
    ↓
helm upgrade --install
    ↓
attend le rollout
    ↓
affiche Deployment / Pod / Service / Ingress / Events
```

## Étape 6 — Validation

```bash
kubectl get pods -n monaco-city-itg
```

Puis :

```bash
kubectl get svc -n monaco-city-itg
```

Puis :

```bash
kubectl get endpoints -n monaco-city-itg
```

---

# 31. Procédure PRP

Sélectionner :

```text
Environnement cible = prp
```

Le pipeline utilise :

```text
BuildImage
    ↓
DeployPRP
```

avec :

```text
Namespace = monaco-city-prp
Values = values-prp.yaml
```

---

# 32. Procédure PROD

Sélectionner :

```text
Environnement cible = prod
```

Le pipeline utilise :

```text
BuildImage
    ↓
DeployPROD
```

avec :

```text
Namespace = monaco-city-prod
Values = values-prod.yaml
```

Pour PROD, il est recommandé de protéger l'environnement Azure DevOps par une approbation manuelle et/ou des checks avant exécution du stage.

---

# 33. Rollback

Le déploiement utilise :

```text
--atomic
```

En cas d'échec, Helm tente automatiquement de revenir à l'état précédent.

Pour consulter l'historique :

```bash
helm history \
  menu-analyst-api-release \
  -n monaco-city-itg
```

Pour revenir explicitement à une révision :

```bash
helm rollback \
  menu-analyst-api-release \
  <REVISION> \
  -n monaco-city-itg
```

Puis :

```bash
kubectl rollout status \
  deployment/<DEPLOYMENT> \
  -n monaco-city-itg
```

---

# 34. Checklist avant mise en production

## Azure DevOps

- [ ] Variable Group `menu-analyst-aks` présent
- [ ] `azureOpenAIEndpoint` renseigné
- [ ] `azureOpenAIDeployment` renseigné
- [ ] `azureOpenAIApiVersion` renseigné
- [ ] `azureOpenAIApiKey` configurée comme secrète
- [ ] `aksResourceGroupITG` renseigné
- [ ] `aksClusterNameITG` renseigné
- [ ] `aksResourceGroupPRP` renseigné
- [ ] `aksClusterNamePRP` renseigné
- [ ] `aksResourceGroupPROD` renseigné
- [ ] `aksClusterNamePROD` renseigné

## Service Connections

- [ ] `AzureYourMonacoDockerRegistry` est de type Docker Registry
- [ ] `ServiceConnection-AKS-ITG` est de type Azure Resource Manager
- [ ] `ServiceConnection-AKS-PRP` est de type Azure Resource Manager
- [ ] `sp-tf-sub-monaco-prod-001` est autorisée pour le pipeline

## ACR

- [ ] ACR accessible
- [ ] repositories existants
- [ ] pipeline autorisé à pousser
- [ ] AKS autorisé en `AcrPull`

## Helm

- [ ] `Chart.yaml`
- [ ] `values.yaml`
- [ ] `values-itg.yaml`
- [ ] `values-prp.yaml`
- [ ] `values-prod.yaml`
- [ ] `helm lint` OK
- [ ] `helm template` OK

## Kubernetes

- [ ] namespaces existants ou créables
- [ ] Deployment créé
- [ ] Pod `Running`
- [ ] Readiness `True`
- [ ] Service créé
- [ ] Endpoints présents
- [ ] Ingress configuré si nécessaire
- [ ] HPA fonctionnel si activé

## API

- [ ] FastAPI écoute sur `0.0.0.0`
- [ ] port container correct
- [ ] health endpoint disponible
- [ ] POST `/api/v1/analyze` fonctionnel
- [ ] accès Azure OpenAI fonctionnel

---

# 35. Commandes de diagnostic essentielles

### Vue générale

```bash
kubectl get all -n monaco-city-itg
```

### Pods

```bash
kubectl get pods -n monaco-city-itg -o wide --show-labels
```

### Service

```bash
kubectl get svc -n monaco-city-itg
```

### Endpoints

```bash
kubectl get endpoints -n monaco-city-itg
```

### Events

```bash
kubectl get events \
  -n monaco-city-itg \
  --sort-by=.metadata.creationTimestamp
```

### Helm

```bash
helm status menu-analyst-api-release \
  -n monaco-city-itg
```

### Historique Helm

```bash
helm history menu-analyst-api-release \
  -n monaco-city-itg
```

### Logs

```bash
kubectl logs \
  <POD> \
  -n monaco-city-itg \
  --all-containers=true \
  --tail=200
```

### Description Pod

```bash
kubectl describe pod \
  <POD> \
  -n monaco-city-itg
```

---

# 36. Architecture cible

```text
                    Client / Pod appelant
                              |
                              | HTTP POST
                              v
                     +----------------+
                     | Kubernetes     |
                     | Service        |
                     +----------------+
                              |
                              v
                     +----------------+
                     | menu-analyst   |
                     | API Pod        |
                     | FastAPI        |
                     +----------------+
                              |
                              | HTTPS
                              v
                    +--------------------+
                    | Azure OpenAI /     |
                    | Azure Foundry      |
                    +--------------------+

Azure DevOps
     |
     +--> Validate
     |
     +--> Docker build
     |
     +--> Docker push
     |
     +--> ACR
             |
             +--> AKS ITG
             +--> AKS PRP
             +--> AKS PROD
```

---

# 37. Point d'attention important sur le pipeline actuel

Le pipeline fourni utilise trois repositories ACR différents selon l'environnement.

Cela signifie que :

```text
Build ITG  → repository ITG
Build PRP  → repository PRP
Build PROD → repository PROD
```

Ainsi, une promotion PRP → PROD ne réutilise pas exactement le même repository d'image.

Si l'objectif est d'obtenir une vraie promotion d'un artefact immuable entre environnements, une architecture plus stricte serait :

```text
Build
  ↓
ACR repository unique
  ↓
tag immuable
  ↓
ITG
  ↓
PRP
  ↓
PROD
```

Cela permettrait de garantir que **le même digest d'image** est testé en ITG puis promu en PRP et PROD.

La configuration actuelle ne met pas en œuvre cette promotion par digest ; elle construit/publie selon l'environnement sélectionné.

---

# 38. Résumé opérationnel

La procédure nominale est :

```text
1. Commit / Push
        ↓
2. Run pipeline
        ↓
3. Choisir ITG / PRP / PROD
        ↓
4. Validate
        ↓
5. BuildImage
        ↓
6. Docker build
        ↓
7. Docker push vers ACR
        ↓
8. Connexion AKS via AzureRM
        ↓
9. Récupération kubeconfig
        ↓
10. Injection des paramètres Azure OpenAI
        ↓
11. Helm lint / template
        ↓
12. Helm upgrade --install
        ↓
13. Rollout
        ↓
14. Vérification Pod
        ↓
15. Vérification Service
        ↓
16. Vérification Endpoints
        ↓
17. Test API
```

Cette procédure constitue le mode opératoire de référence pour le déploiement de `menu-analyst-api` dans les environnements ITG, PRP et PROD.
