/*
 * proxy.c - A concurrent HTTP/1.0 web proxy
 * Compile: gcc proxy.c -o proxy
 * Run:     ./proxy <port>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <netdb.h>
#include <signal.h>

#define BUF 65536
#define MAX_CHILD 100

volatile int nchild = 0;

/* Reap zombie child processes */
void sigchld_handler(int sig) {
    while (waitpid(-1, NULL, WNOHANG) > 0)
        nchild--;
}

/* Send HTTP error response to client */
void send_error(int fd, int code, char *msg) {
    char buf[256];
    int n = sprintf(buf,
        "HTTP/1.0 %d %s\r\nContent-Type: text/html\r\n\r\n"
        "<h1>%d %s</h1>\r\n", code, msg, code, msg);
    write(fd, buf, n);
}

/* Parse absolute URI: http://host[:port]/path */
int parse_url(char *url, char *host, int *port, char *path) {
    if (strncmp(url, "http://", 7) != 0) return -1;

    char *h = url + 7;                     /* skip "http://" */
    char *slash = strchr(h, '/');           /* find start of path */
    char *colon = strchr(h, ':');           /* find port separator */
    int hlen = (slash ? slash : h + strlen(h)) - h;

    strcpy(path, slash ? slash : "/");      /* extract path */

    if (colon && colon < h + hlen) {        /* port specified */
        strncpy(host, h, colon - h);
        host[colon - h] = '\0';
        *port = atoi(colon + 1);
    } else {                                /* default port 80 */
        strncpy(host, h, hlen);
        host[hlen] = '\0';
        *port = 80;
    }
    return (strlen(host) > 0 && *port > 0 && *port <= 65535) ? 0 : -1;
}

/* Validate headers: each line must have "Name: Value\r\n" format */
int validate_headers(char *hdr) {
    while (*hdr && !(hdr[0] == '\r' && hdr[1] == '\n')) {
        char *eol = strstr(hdr, "\r\n");
        if (!eol) return -1;                           /* missing CRLF */
        if (!memchr(hdr, ':', eol - hdr) || hdr[0] == ':')
            return -1;                                 /* no colon or empty name */
        hdr = eol + 2;
    }
    return 0;
}

/* Handle one client connection */
void handle_client(int cfd) {
    char buf[BUF], method[16], url[4096], ver[16];
    char host[256], path[4096], req[BUF];
    int port, n, total = 0;

    /* 1. Read full request from client */
    while (total < BUF - 1) {
        n = read(cfd, buf + total, BUF - 1 - total);
        if (n <= 0) break;
        total += n;
        buf[total] = '\0';
        if (strstr(buf, "\r\n\r\n")) break;    /* headers complete */
    }
    if (total <= 0) return;

    /* 2. Parse request line: METHOD URI HTTP/1.0 */
    char *eol = strstr(buf, "\r\n");
    if (!eol) { send_error(cfd, 400, "Bad Request"); return; }

    *eol = '\0';
    if (sscanf(buf, "%15s %4095s %15s", method, url, ver) != 3 ||
        strncmp(ver, "HTTP/", 5) != 0) {
        send_error(cfd, 400, "Bad Request"); return;
    }
    *eol = '\r';

    /* 3. Only GET is supported */
    if (strcmp(method, "GET") != 0) {
        send_error(cfd, 501, "Not Implemented"); return;
    }

    /* 4. Validate all header lines */
    char *headers = eol + 2;
    if (validate_headers(headers) < 0) {
        send_error(cfd, 400, "Bad Request"); return;
    }

    /* 5. Parse URL into host, port, path */
    if (parse_url(url, host, &port, path) < 0) {
        send_error(cfd, 400, "Bad Request"); return;
    }

    /* 6. Connect to remote server */
    struct hostent *he = gethostbyname(host);
    if (!he) { send_error(cfd, 404, "Not Found"); return; }

    int sfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sfd < 0) { send_error(cfd, 500, "Internal Server Error"); return; }

    struct sockaddr_in saddr = {0};
    saddr.sin_family = AF_INET;
    memcpy(&saddr.sin_addr, he->h_addr, he->h_length);
    saddr.sin_port = htons(port);

    if (connect(sfd, (struct sockaddr *)&saddr, sizeof(saddr)) < 0) {
        send_error(cfd, 502, "Bad Gateway"); close(sfd); return;
    }

    /* 7. Forward request with relative URI and HTTP/1.0 */
    int rlen = sprintf(req, "GET %s HTTP/1.0\r\n%s", path, headers);
    write(sfd, req, rlen);

    /* 8. Relay server response back to client */
    while ((n = read(sfd, buf, BUF)) > 0)
        write(cfd, buf, n);

    close(sfd);
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <port>\n", argv[0]);
        return 1;
    }
    int port = atoi(argv[1]);

    signal(SIGCHLD, sigchld_handler);

    /* Create listening socket */
    int lfd = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;  /* listen on all interfaces */
    addr.sin_port = htons(port);

    if (bind(lfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind"); return 1;
    }
    listen(lfd, 10);
    printf("Proxy running on port %d\n", port);

    /* Accept loop */
    while (1) {
        struct sockaddr_in caddr;
        socklen_t clen = sizeof(caddr);
        int cfd = accept(lfd, (struct sockaddr *)&caddr, &clen);
        if (cfd < 0) continue;

        if (nchild >= MAX_CHILD) {          /* enforce process limit */
            send_error(cfd, 503, "Service Unavailable");
            close(cfd); continue;
        }

        pid_t pid = fork();
        if (pid == 0) {                     /* child handles request */
            close(lfd);
            handle_client(cfd);
            close(cfd);
            exit(0);
        } else if (pid > 0) {              /* parent keeps listening */
            nchild++;
            close(cfd);
        } else {                            /* fork failed */
            send_error(cfd, 500, "Internal Server Error");
            close(cfd);
        }
    }
}
