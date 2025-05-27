{{/*
Expand the name of the chart.
*/}}
{{- define "hono-load-test.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "hono-load-test.fullname" -}}
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
{{- define "hono-load-test.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "hono-load-test.labels" -}}
helm.sh/chart: {{ include "hono-load-test.chart" . }}
{{ include "hono-load-test.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "hono-load-test.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hono-load-test.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service account name
*/}}
{{- define "hono-load-test.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "hono-load-test.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Determine image repository
*/}}
{{- define "hono-load-test.image" -}}
{{- $repo := .Values.image.repository -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end }}

{{/*
Service-specific image repository
*/}}
{{- define "hono-load-test.serviceImage" -}}
{{- $service := .service -}}
{{- $global := .global -}}
{{- $repo := $service.image.repository | default $global.image.repository -}}
{{- $tag := $service.image.tag | default $global.image.tag | default $global.Chart.AppVersion -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end }}

{{/*
Create volume claim name
*/}}
{{- define "hono-load-test.pvcName" -}}
{{- printf "%s-data" (include "hono-load-test.fullname" .) }}
{{- end }}
