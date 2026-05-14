{{- define "devops-info-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "devops-info-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "devops-info-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "devops-info-service.labels" -}}
helm.sh/chart: {{ include "devops-info-service.chart" . }}
{{ include "devops-info-service.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "devops-info-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "devops-info-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "devops-info-service.envVars" -}}
{{- range .Values.env }}
- name: {{ .name }}
  value: {{ .value | quote }}
{{- end }}
{{- end }}

{{- define "devops-info-service.initContainers" -}}
{{- if .Values.initContainers.download.enabled }}
- name: init-download
  image: {{ .Values.initContainers.download.image | quote }}
  command:
    - sh
    - -c
    - |
      set -eux
      echo "[init-download] fetching {{ .Values.initContainers.download.url }}"
      wget -q -O {{ .Values.initContainers.download.targetFile }} {{ .Values.initContainers.download.url }}
      echo "[init-download] saved $(wc -c < {{ .Values.initContainers.download.targetFile }}) bytes"
  volumeMounts:
    - name: init-data
      mountPath: {{ .Values.initContainers.download.mountPath }}
{{- end }}
{{- if .Values.initContainers.waitForService.enabled }}
- name: wait-for-service
  image: {{ .Values.initContainers.waitForService.image | quote }}
  command:
    - sh
    - -c
    - |
      set -eu
      echo "[wait-for-service] resolving {{ .Values.initContainers.waitForService.service }} ..."
      deadline=$(( $(date +%s) + {{ .Values.initContainers.waitForService.timeoutSeconds }} ))
      until nslookup {{ .Values.initContainers.waitForService.service }} >/dev/null 2>&1; do
        if [ "$(date +%s)" -ge "$deadline" ]; then
          echo "[wait-for-service] timed out after {{ .Values.initContainers.waitForService.timeoutSeconds }}s"
          exit 1
        fi
        echo "  not ready yet, sleeping 2s"
        sleep 2
      done
      echo "[wait-for-service] dependency reachable"
{{- end }}
{{- end }}

{{- define "devops-info-service.initVolumeMount" -}}
{{- if .Values.initContainers.download.enabled }}
- name: init-data
  mountPath: {{ .Values.initContainers.download.mountPath }}
  readOnly: true
{{- end }}
{{- end }}

{{- define "devops-info-service.initVolume" -}}
{{- if .Values.initContainers.download.enabled }}
- name: init-data
  emptyDir: {}
{{- end }}
{{- end }}
