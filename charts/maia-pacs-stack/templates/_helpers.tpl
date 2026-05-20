{{/*
Expand the name of the chart.
*/}}
{{- define "maia-pacs-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "maia-pacs-stack.fullname" -}}
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

{{- define "maia-pacs-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "maia-pacs-stack.labels" -}}
helm.sh/chart: {{ include "maia-pacs-stack.chart" . }}
{{ include "maia-pacs-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "maia-pacs-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "maia-pacs-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "maia-pacs-stack.ohifSelectorLabels" -}}
{{ include "maia-pacs-stack.selectorLabels" . }}
app.kubernetes.io/component: ohif
{{- end }}

{{- define "maia-pacs-stack.oauth2ProxySelectorLabels" -}}
{{ include "maia-pacs-stack.selectorLabels" . }}
app.kubernetes.io/component: oauth2-proxy
{{- end }}

{{- define "maia-pacs-stack.nginxSelectorLabels" -}}
{{ include "maia-pacs-stack.selectorLabels" . }}
app.kubernetes.io/component: nginx
{{- end }}

{{- define "maia-pacs-stack.postgresSelectorLabels" -}}
{{ include "maia-pacs-stack.selectorLabels" . }}
app.kubernetes.io/component: postgres
{{- end }}

{{- define "maia-pacs-stack.postgresServiceHost" -}}
{{- default (printf "%s-postgres" (include "maia-pacs-stack.fullname" .)) .Values.postgres.service.host }}
{{- end }}

{{- define "maia-pacs-stack.ohifConfigMapName" -}}
{{- printf "%s-ohif-config" (include "maia-pacs-stack.fullname" .) }}
{{- end }}

{{- define "maia-pacs-stack.nginxConfigMapName" -}}
{{- printf "%s-nginx-config" (include "maia-pacs-stack.fullname" .) }}
{{- end }}

{{- define "maia-pacs-stack.ohifServiceHost" -}}
{{- default (printf "%s-ohif" (include "maia-pacs-stack.fullname" .)) .Values.nginx.upstreams.ohif }}
{{- end }}

{{- define "maia-pacs-stack.oauth2ProxyServiceHost" -}}
{{- default (printf "%s-oauth2-proxy" (include "maia-pacs-stack.fullname" .)) .Values.nginx.upstreams.oauth2Proxy }}
{{- end }}

{{- define "maia-pacs-stack.orthancSelectorLabels" -}}
{{ include "maia-pacs-stack.selectorLabels" . }}
app.kubernetes.io/component: orthanc
{{- end }}

{{- define "maia-pacs-stack.orthancServiceHost" -}}
{{- default (printf "%s-orthanc" (include "maia-pacs-stack.fullname" .)) .Values.orthanc.service.host }}
{{- end }}

{{- define "maia-pacs-stack.orthancUpstreamHost" -}}
{{- default (include "maia-pacs-stack.orthancServiceHost" .) .Values.nginx.upstreams.orthanc }}
{{- end }}

{{- define "maia-pacs-stack.orthancConfigMapName" -}}
{{- printf "%s-orthanc-config" (include "maia-pacs-stack.fullname" .) }}
{{- end }}

{{- define "maia-pacs-stack.orthancStoragePvcName" -}}
{{- printf "%s-orthanc-storage" (include "maia-pacs-stack.fullname" .) }}
{{- end }}

{{- define "maia-pacs-stack.orthancOhifConfigRouterBasename" -}}
{{- coalesce .Values.orthanc.ohifConfigJs.routerBasename .Values.maiaPaths.ohifPublicPath }}
{{- end }}

{{- define "maia-pacs-stack.orthancOhifConfigWadoUriRoot" -}}
{{- coalesce .Values.orthanc.ohifConfigJs.wadoUriRoot .Values.maiaPaths.dicomwebPublicPath }}
{{- end }}

{{- define "maia-pacs-stack.orthancOhifConfigQidoRoot" -}}
{{- coalesce .Values.orthanc.ohifConfigJs.qidoRoot .Values.maiaPaths.dicomwebPublicPath }}
{{- end }}

{{- define "maia-pacs-stack.orthancOhifConfigWadoRoot" -}}
{{- coalesce .Values.orthanc.ohifConfigJs.wadoRoot .Values.maiaPaths.dicomwebPublicPath }}
{{- end }}

{{- define "maia-pacs-stack.orthancOhifConfig" -}}
{{- $rb := include "maia-pacs-stack.orthancOhifConfigRouterBasename" . | trim }}
{{- $wadouri := include "maia-pacs-stack.orthancOhifConfigWadoUriRoot" . | trim }}
{{- $qido := include "maia-pacs-stack.orthancOhifConfigQidoRoot" . | trim }}
{{- $wado := include "maia-pacs-stack.orthancOhifConfigWadoRoot" . | trim }}
{{- .Files.Get "files/orthanc-ohif-config.js" | replace "routerBasename: '/ohif-xyz/'" (printf "routerBasename: '%s'" $rb) | replace "wadoUriRoot: '/dicom-web-xyz'" (printf "wadoUriRoot: '%s'" $wadouri) | replace "qidoRoot: '/dicom-web-xyz'" (printf "qidoRoot: '%s'" $qido) | replace "wadoRoot: '/dicom-web-xyz'" (printf "wadoRoot: '%s'" $wado) }}
{{- end }}

{{- define "maia-pacs-stack.orthancJsonConfig" -}}
{{- $pgHost := default (include "maia-pacs-stack.postgresServiceHost" .) .Values.orthanc.config.postgresHost }}
{{- .Files.Get "files/orthancv2.0.json" | replace "orthanc-index" $pgHost }}
{{- end }}

{{- define "maia-pacs-stack.orthancDicomWebPublicRoot" -}}
{{- printf "%s/dicom-web/" .Values.maiaPaths.orthancPublicPath }}
{{- end }}

{{- define "maia-pacs-stack.orthancOhifViewerPublicRoot" -}}
{{- printf "%s%s" .Values.maiaPaths.maiaPublicUrl .Values.maiaPaths.ohifPublicPath }}
{{- end }}

{{- define "maia-pacs-stack.maiaAgentSelectorLabels" -}}
{{ include "maia-pacs-stack.selectorLabels" . }}
app.kubernetes.io/component: maia-agent
{{- end }}

{{- define "maia-pacs-stack.maiaAgentServiceHost" -}}
{{- default (printf "%s-maia-agent" (include "maia-pacs-stack.fullname" .)) .Values.nginx.upstreams.maiaAgent }}
{{- end }}

{{- define "maia-pacs-stack.maiaAgentDicomwebUrl" -}}
{{- if .Values.maiaAgent.dicomweb.url }}
{{- .Values.maiaAgent.dicomweb.url }}
{{- else }}
{{- printf "http://%s:%v/dicom-web" (include "maia-pacs-stack.orthancUpstreamHost" .) .Values.orthanc.service.targetPort }}
{{- end }}
{{- end }}

{{- define "maia-pacs-stack.maiaAgentPvcName" -}}
{{- printf "%s-maia-agent-data" (include "maia-pacs-stack.fullname" .) }}
{{- end }}

{{- define "maia-pacs-stack.oauth2ProxyRedirectUrl" -}}
{{- printf "%s%s/callback" .Values.maiaPaths.maiaPublicUrl .Values.maiaPaths.oauth2PublicPath }}
{{- end }}
