{{/*
Expand the name of the chart.
*/}}
{{- define "django-ninja-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "django-ninja-stack.fullname" -}}
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
{{- define "django-ninja-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "django-ninja-stack.labels" -}}
helm.sh/chart: {{ include "django-ninja-stack.chart" . }}
{{ include "django-ninja-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "django-ninja-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "django-ninja-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "django-ninja-stack.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "django-ninja-stack.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database URL
*/}}
{{- define "django-ninja-stack.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgres://%s:%s@%s-postgresql:5432/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password (include "django-ninja-stack.fullname" .) .Values.postgresql.auth.database }}
{{- else if .Values.externalDatabase }}
{{- printf "postgres://%s:%s@%s:%s/%s" .Values.externalDatabase.user .Values.externalDatabase.password .Values.externalDatabase.host (toString .Values.externalDatabase.port) .Values.externalDatabase.database }}
{{- end }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "django-ninja-stack.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s-redis-master:6379/0" (include "django-ninja-stack.fullname" .) }}
{{- else if .Values.externalRedis }}
{{- if .Values.externalRedis.password }}
{{- printf "redis://:%s@%s:%s/0" .Values.externalRedis.password .Values.externalRedis.host (toString .Values.externalRedis.port) }}
{{- else }}
{{- printf "redis://%s:%s/0" .Values.externalRedis.host (toString .Values.externalRedis.port) }}
{{- end }}
{{- end }}
{{- end }}
