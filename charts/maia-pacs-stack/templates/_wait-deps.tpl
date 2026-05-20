{{/*
Init containers approximate docker-compose depends_on ordering:
  orthanc -> postgres
  ohif -> orthanc
  maia-agent -> orthanc (DICOMWEB_URL)
  nginx -> orthanc, ohif, maia-agent
*/}}
{{- define "maia-pacs-stack.waitDepsImage" -}}
{{- printf "%s:%s" .Values.waitForDependencies.image.repository .Values.waitForDependencies.image.tag }}
{{- end }}

{{- define "maia-pacs-stack.initOrthancWaitPostgres" -}}
{{- if and .Values.waitForDependencies.enabled .Values.waitForDependencies.orthanc.waitForPostgres }}
- name: wait-for-postgres
  image: {{ include "maia-pacs-stack.waitDepsImage" . | quote }}
  command:
    - sh
    - -c
    - until nc -z "$PG_HOST" "$PG_PORT"; do echo waiting for postgres; sleep 2; done
  env:
    - name: PG_HOST
      value: {{ include "maia-pacs-stack.postgresServiceHost" . | quote }}
    - name: PG_PORT
      value: {{ .Values.postgres.service.targetPort | quote }}
  {{- with .Values.waitForDependencies.resources }}
  resources:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
{{- end }}

{{- define "maia-pacs-stack.initOhifWaitOrthanc" -}}
{{- if and .Values.waitForDependencies.enabled .Values.waitForDependencies.ohif.waitForOrthanc }}
- name: wait-for-orthanc
  image: {{ include "maia-pacs-stack.waitDepsImage" . | quote }}
  command:
    - sh
    - -c
    - until nc -z "$ORTHANC_HOST" "$ORTHANC_PORT"; do echo waiting for orthanc; sleep 2; done
  env:
    - name: ORTHANC_HOST
      value: {{ include "maia-pacs-stack.orthancUpstreamHost" . | quote }}
    - name: ORTHANC_PORT
      value: {{ .Values.orthanc.service.targetPort | quote }}
  {{- with .Values.waitForDependencies.resources }}
  resources:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
{{- end }}

{{- define "maia-pacs-stack.initMaiaAgentWaitOrthanc" -}}
{{- if and .Values.waitForDependencies.enabled .Values.waitForDependencies.maiaAgent.waitForOrthanc }}
- name: wait-for-orthanc
  image: {{ include "maia-pacs-stack.waitDepsImage" . | quote }}
  command:
    - sh
    - -c
    - until nc -z "$ORTHANC_HOST" "$ORTHANC_PORT"; do echo waiting for orthanc; sleep 2; done
  env:
    - name: ORTHANC_HOST
      value: {{ include "maia-pacs-stack.orthancUpstreamHost" . | quote }}
    - name: ORTHANC_PORT
      value: {{ .Values.orthanc.service.targetPort | quote }}
  {{- with .Values.waitForDependencies.resources }}
  resources:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
{{- end }}

{{- define "maia-pacs-stack.initNginxWaitBackends" -}}
{{- if .Values.waitForDependencies.enabled }}
{{- if .Values.waitForDependencies.nginx.waitForOrthanc }}
- name: wait-for-orthanc
  image: {{ include "maia-pacs-stack.waitDepsImage" . | quote }}
  command:
    - sh
    - -c
    - until nc -z "$ORTHANC_HOST" "$ORTHANC_PORT"; do echo waiting for orthanc; sleep 2; done
  env:
    - name: ORTHANC_HOST
      value: {{ include "maia-pacs-stack.orthancUpstreamHost" . | quote }}
    - name: ORTHANC_PORT
      value: {{ .Values.orthanc.service.targetPort | quote }}
  {{- with .Values.waitForDependencies.resources }}
  resources:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
{{- if .Values.waitForDependencies.nginx.waitForOhif }}
- name: wait-for-ohif
  image: {{ include "maia-pacs-stack.waitDepsImage" . | quote }}
  command:
    - sh
    - -c
    - until nc -z "$OHIF_HOST" "$OHIF_PORT"; do echo waiting for ohif; sleep 2; done
  env:
    - name: OHIF_HOST
      value: {{ include "maia-pacs-stack.ohifServiceHost" . | quote }}
    - name: OHIF_PORT
      value: {{ .Values.service.targetPort | quote }}
  {{- with .Values.waitForDependencies.resources }}
  resources:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
{{- if .Values.waitForDependencies.nginx.waitForMaiaAgent }}
- name: wait-for-maia-agent
  image: {{ include "maia-pacs-stack.waitDepsImage" . | quote }}
  command:
    - sh
    - -c
    - until nc -z "$AGENT_HOST" "$AGENT_PORT"; do echo waiting for maia-agent; sleep 2; done
  env:
    - name: AGENT_HOST
      value: {{ include "maia-pacs-stack.maiaAgentServiceHost" . | quote }}
    - name: AGENT_PORT
      value: {{ .Values.maiaAgent.service.targetPort | quote }}
  {{- with .Values.waitForDependencies.resources }}
  resources:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
{{- end }}
{{- end }}
