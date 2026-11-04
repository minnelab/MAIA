{{- define "ehrbase.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ehrbase.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "ehrbase.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end }}

{{- define "ehrbase.labels" -}}
helm.sh/chart: {{ include "ehrbase.chart" . }}
{{ include "ehrbase.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "ehrbase.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ehrbase.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "ehrbase.ehrbase.name" -}}
{{- printf "%s-ehrbase" (include "ehrbase.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ehrbase.ehrbase.ingress.name" -}}
{{- printf "%s-ehrbase-http" (include "ehrbase.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ehrbase.ehrdb.name" -}}
{{- printf "%s-ehrdb" (include "ehrbase.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ehrbase.keycloak.name" -}}
{{- printf "%s-keycloak" (include "ehrbase.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ehrbase.envConfigMap.name" -}}
{{- printf "%s-env-ehrbase" (include "ehrbase.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ehrbase.keycloak.realmConfigMap.name" -}}
{{- printf "%s-keycloak-realm" (include "ehrbase.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
  DB credentials Secret. MAIA/maia_fn.py looks up this same name:
  "<namespace>-ehrbase-db" (63 chars, one trailing hyphen removed).
*/}}
{{- define "ehrbase.db.secretName" -}}
{{- printf "%s-ehrbase-db" .Release.Namespace | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ehrbase.jdbcUrl" -}}
{{- if .Values.ehrbase.db.url }}
{{- .Values.ehrbase.db.url }}
{{- else }}
jdbc:postgresql://{{ include "ehrbase.ehrdb.name" . }}:{{ .Values.ehrdb.service.port }}/{{ .Values.ehrdb.database.name }}
{{- end }}
{{- end }}
