{{- define "agent-runtime.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "agent-runtime.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "agent-runtime.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "agent-runtime.labels" -}}
app.kubernetes.io/name: {{ include "agent-runtime.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
