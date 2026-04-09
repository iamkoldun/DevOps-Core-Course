{{- define "devops-info-service-v2.name" -}}
{{- include "common.name" . }}
{{- end }}

{{- define "devops-info-service-v2.fullname" -}}
{{- include "common.fullname" . }}
{{- end }}

{{- define "devops-info-service-v2.chart" -}}
{{- include "common.chart" . }}
{{- end }}

{{- define "devops-info-service-v2.labels" -}}
{{- include "common.labels" . }}
{{- end }}

{{- define "devops-info-service-v2.selectorLabels" -}}
{{- include "common.selectorLabels" . }}
{{- end }}
