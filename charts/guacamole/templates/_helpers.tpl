{{/*
Expand the name of the chart.
*/}}
{{- define "guacamole.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "guacamole.fullname" -}}
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

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "guacamole.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "guacamole.guacamoleLabels" -}}
helm.sh/chart: {{ include "guacamole.chart" . }}
{{ include "guacamole.guacamoleSelectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}


{{/*
Common labels
*/}}
{{- define "guacamole.guacdLabels" -}}
helm.sh/chart: {{ include "guacamole.chart" . }}
{{ include "guacamole.guacdSelectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "guacamole.guacamoleSelectorLabels" -}}
app.kubernetes.io/name: {{ include "guacamole.name" . }}-guacamole
app.kubernetes.io/instance: {{ .Release.Name }}-guacamole
{{- end }}

{{/*
Selector labels
*/}}
{{- define "guacamole.guacdSelectorLabels" -}}
app.kubernetes.io/name: {{ include "guacamole.name" . }}-guacd
app.kubernetes.io/instance: {{ .Release.Name }}-guacd
{{- end }}

{{/*
Common labels for postgresql
*/}}
{{- define "guacamole.postgresqlLabels" -}}
helm.sh/chart: {{ include "guacamole.chart" . }}
{{ include "guacamole.postgresqlSelectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels for postgresql
*/}}
{{- define "guacamole.postgresqlSelectorLabels" -}}
app.kubernetes.io/name: {{ include "guacamole.name" . }}-postgresql
app.kubernetes.io/instance: {{ .Release.Name }}-postgresql
{{- end }}

{{/*
Common labels for webtop
*/}}
{{- define "guacamole.webtopLabels" -}}
helm.sh/chart: {{ include "guacamole.chart" . }}
{{ include "guacamole.webtopSelectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels for webtop
*/}}
{{- define "guacamole.webtopSelectorLabels" -}}
app.kubernetes.io/name: {{ include "guacamole.name" . }}-webtop
app.kubernetes.io/instance: {{ .Release.Name }}-webtop
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "guacamole.serviceAccountName" -}}
{{- if .Values.guacamole.serviceAccount.create }}
{{- default (include "guacamole.fullname" .) .Values.guacamole.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.guacamole.serviceAccount.name }}
{{- end }}
{{- end }}
