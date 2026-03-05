FROM alpine:latest
RUN apk add --quiet gcc musl-dev
COPY proxy.c /app/proxy.c
RUN gcc /app/proxy.c -o /app/proxy
EXPOSE 8080
CMD ["/app/proxy", "8080"]
