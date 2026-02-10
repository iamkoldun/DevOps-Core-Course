FROM golang:1.21-alpine AS builder

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o devops-info-service main.go

FROM alpine:3.19

RUN addgroup -g 1000 -S appgroup \
    && adduser -u 1000 -S appuser -G appgroup

WORKDIR /app

COPY --from=builder /build/devops-info-service .

RUN chown appuser:appgroup devops-info-service

USER appuser

EXPOSE 8080

ENV HOST=0.0.0.0
ENV PORT=8080

CMD ["./devops-info-service"]
