# ADR 031: Caddy vs Nginx vs Traefik (Why Caddy?)

**Status:** Draft

## Context
As Syndra grows, its services (Data API, Vector DB and Prefect Server) require a robust, secure, and production-grade reverse proxy and TLS termination layer. The initial infrastructure relied on Docker Compose defaults or direct host exposure; however, the need for automated SSL/TLS certificates, production-grade routing, load balancing (future-proof), and security hardening necessitates a formal evaluation of the leading reverse proxy solutions: Caddy, Nginx, and Traefik.

## Decision

### Caddy

Caddy is a **modern, open-source HTTP/2 and HTTP/3 server** that is widely regarded as the **easiest to use reverse proxy for Docker and Kubernetes**. It is known for its automatic TLS certificate management with Let's Encrypt, its simple configuration syntax, and its robust feature set, including HTTP/2 and HTTP/3 support, automatic HTTP-to-HTTPS redirection, and plugin architecture.

### Nginx

Nginx is a **high-performance, open-source HTTP and reverse proxy server** that is widely used in production environments. It is known for its **scalability**, its ability to handle high traffic volumes, and its extensive feature set, including HTTP/2 and HTTP/3 support, automatic HTTP-to-HTTPS redirection, and plugin architecture.

### Traefik

Traefik is a **modern, open-source reverse proxy and load balancer** that is designed for **containerized environments**. It is known for its automatic service discovery, its ability to handle dynamic environments, and its robust feature set, including HTTP/2 and HTTP/3 support, automatic HTTP-to-HTTPS redirection, and plugin architecture.

### Final Decision

**Caddy** was chosen as the reverse proxy **for Syndra due to its extreme simplicity, automatic HTTPS out of the box, and minimal configuration overhead**. While Nginx offers more granular control and Traefik excels in complex Kubernetes environments, Caddy provides the perfect balance of features and ease of use for our current VPS-based infrastructure. Its clean Caddyfile syntax and automatic Let's Encrypt integration allow us to deploy a secure reverse proxy in minutes without the complexity of managing certificates and routing rules manually.

## Consequences

- **Positive:** Caddy is extremely easy to set up and use. It is also very lightweight and has a small memory footprint. It is also very easy to set up automatic HTTPS with Let's Encrypt. It is also very easy to set up automatic HTTP-to-HTTPS redirection.
- **Negative:** Caddy is not as widely used as Nginx or Traefik, which means there is less community support and fewer resources available online.

## Sources
> **Source 1:** [https://bigmike.help/en/posts/102/](https://bigmike.help/en/posts/102/)

> **Source 2:** [https://www.reddit.com/r/VPS/comments/15v259v/nginx_vs_traefik_vs_caddy_for_a_personal_server/](https://www.reddit.com/r/VPS/comments/15v259v/nginx_vs_traefik_vs_caddy_for_a_personal_server/)