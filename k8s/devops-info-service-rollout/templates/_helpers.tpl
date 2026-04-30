{{- define "devops-info-service-rollout.name" -}}
{{- include "common.name" . }}
{{- end }}

{{- define "devops-info-service-rollout.fullname" -}}
{{- include "common.fullname" . }}
{{- end }}

{{- define "devops-info-service-rollout.chart" -}}
{{- include "common.chart" . }}
{{- end }}

{{- define "devops-info-service-rollout.labels" -}}
{{- include "common.labels" . }}
{{- end }}

{{- define "devops-info-service-rollout.selectorLabels" -}}
{{- include "common.selectorLabels" . }}
{{- end }}
