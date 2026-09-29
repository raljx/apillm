{{/*
Nom de l'application.
*/}}
{{- define "menu-analyst-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Nom complet de l'application.
*/}}
{{- define "menu-analyst-api.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := include "menu-analyst-api.name" . }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Nom du chart.
*/}}
{{- define "menu-analyst-api.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels communs.
*/}}
{{- define "menu-analyst-api.labels" -}}
helm.sh/chart: {{ include "menu-analyst-api.chart" . }}
app.kubernetes.io/name: {{ include "menu-analyst-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Labels utilisés pour le selector.
*/}}
{{- define "menu-analyst-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "menu-analyst-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Nom du ServiceAccount.
*/}}
{{- define "menu-analyst-api.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "menu-analyst-api.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}